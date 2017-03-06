import numpy as np
from scipy.integrate import nquad
import scipy.stats as stats
from pylab import *
import lab
import time

# TODO/NOTE
#
# fit_bayes_1
# va esponenziale nel numero di parametri, è ragionevole fino a due parametri
# 1 parametro: un cazzo
# 2 parametri: 1 secondo
# 3 parametri: 2 minuti
# 4 parametri: non ci ho provato, 4 ore?
# approssima tagliando gli estremi di integrazione (anche se nquad potrebbe integrare fino a ±∞), bisogna modificarlo in modo che il taglio segua la correlazione, quindi l'argomento dp0 va rimpiazzato con un covp0, al momento l'errore per difetto è talvolta visibile.
# si può ancora guadagnare un fattore costante parallelizzando gli integrali, girando un po' le cose dovrebbero essere TUTTI indipendenti a meno di overflow
# la posteriori iniziale non normalizzata mi sa che va in overflow con abbastanza dati, con 10000 ci sta ancora, con 100000 di punti non mi fiderei
# bisogna poter dare i priori!
# di sicuro questa funzione non va bene con gli errori sulle x perché lì ogni x è un parametro
#
# bisogna fare un fit_bayes_2 che usi monte carlo
# metodi possibili:
# 0) sampling uniforme ignorante
# 1) sampling gaussiano basato su p0, covp0
# 2) sampling furbo che spara N uniformi, se la varianza è ancora alta divide lungo x_0 e va avanti ricorsivo (ciclando x_1, x_2, etc altrimenti la suddivisione a cubetti porta un andamento esponenziale)
# 3) impacchettare emcee (mi spaventa scegliere in automatico il burn-in)

f = lambda x, a, b: a * x**2 + b*x #+ c
p0 = (-1000, -1000)#, -1)
x = linspace(0, 1, 10000)
dy = np.array([50] * len(x))

y = f(x, *p0) + randn(len(x)) * dy

def fit_bayes_1(f, x, y, dy, p0, dp0):
	p0 = asarray(p0)
	dp0 = asarray(dp0)
	
	prod_dp0 = np.prod(dp0)
	
	# 10^(-3/2) because we show errors with "1.5" digits
	# 1/2 to round correctly
	# 1/2 because the are two sources of error, one is sistematic
	# 1/√2 because everything gets multiplied by normalization
	relerr = 10 ** (-3/2) * 1/2 * 1/2 * 1/np.sqrt(2)
	
	# lim = 1 / sqrt(epsrel) # cebichev inequality
	flim = lambda epsrel: abs(stats.norm.ppf(epsrel / 3))
	fopts = lambda epsrel: dict(epsabs=0, epsrel=epsrel)
	
	idy2 = 1 / dy ** 2
	chi20 = np.sum((y - f(x, *p0))**2 * idy2)
	def L(*p):
		# must be centered around the maximum
		# also we must be careful with overflow/underflow
		# return np.exp(-0.5 * np.sum(((y - f(x, *p)) / dy)**2))
		# return np.prod(np.exp(-((y - f(x, *p)) / dy)**2 / 2) / (np.sqrt(2 * np.pi) * dy))
		# return np.exp((-np.sum(((y - f(x, *p)) / dy)**2) + len(x) - len(p0)) / 2)
		return np.exp((-np.sum((y - f(x, *p))**2 * idy2) + chi20) / 2)
	
	# NORMALIZATION
	
	# we change variable such that the function is already with integral about 1 (we hope)
	# and that the horizontal scale is about 1
	def fint(*p):
		p = np.array(p) * dp0 + p0
		return L(*p)
	
	epsrel = 1 / np.sqrt(len(p0)) * relerr * min(dp0 / np.abs(p0)) # quadrature relative errors sum
	lim = flim(epsrel)
	
	start = time.time()
	N, dN, out = nquad(fint, [(-lim, lim)] * len(p0), opts=fopts(epsrel), full_output=True)
	deltat = time.time() - start
	
	print('Normalization = %s, lim: ±%.1f, epsrel: %.2g, neval: %d' % (lab.xe(N, dN), lim, epsrel, out['neval']))

	fa = linspace(-3, 3, 1000)
	
	figure(0)
	clf()
	suptitle('Normalization')
	for i in range(len(p0)):
		subplot(len(p0), 1, i + 1)
		p = zeros(len(p0))
		def fplot(pi):
			p[i] = pi
			return fint(*p)
		plot(fa, [fplot(A) for A in fa], label='Time: %.3g s' % (deltat,))
		if i == 0:
			legend()
	
	figure(1)
	clf()
	suptitle('Average and covariance')

	par = np.empty(len(p0))
	for i in range(len(par)):
		def fint(*p):
			p = np.array(p) * dp0 + p0
			return p[i] * L(*p)
		epsrel = 1 / np.sqrt(len(p0)) * relerr * dp0[i] / abs(p0[i])
		lim = flim(epsrel)
		start = time.time()
		par[i], err, out = nquad(fint, [(-lim, lim)] * len(p0), opts=fopts(epsrel), full_output=True)
		par[i] /= N
		err /= N
		deltat = time.time() - start
		
		print('Average_%d = %s, lim: ±%.1f, epsrel: %.2g, neval: %d' % (i, lab.xe(par[i], err), lim, epsrel, out['neval']))
		
		subplot(len(p0), len(p0) + 1, i * (len(p0) + 1) + 1)
		p = zeros(len(p0))
		def fplot(pi):
			p[i] = pi
			return fint(*p)
		plot(fa, [fplot(A) for A in fa], label='Time: %.3g s' % (deltat,))
		legend()

	cov = np.empty((len(par), len(par)))
	for i in range(len(par)):
		for j in range(i + 1):
			def fint(*p):
				p = np.array(p) * dp0 + par
				return (p[i] - par[i]) * (p[j] - par[j]) * L(*p)
			epsrel = 1 / np.sqrt(len(p0)) * relerr / sqrt(2)
			lim = flim(epsrel)
			start = time.time()
			cov[i, j], err, out = nquad(fint, [(-lim, lim)] * len(p0), opts=fopts(epsrel), full_output=True)
			cov[i, j] /= N
			err /= N
			deltat = time.time() - start
			cov[j, i] = cov[i, j]
			
			print('Covariance_%d,%d = %s, lim: ±%.1f, epsrel: %.2g, neval: %d' % (i, j, lab.xe(cov[i, j], err), lim, epsrel, out['neval']))
		
			subplot(len(p0), len(p0) + 1, i * (len(p0) + 1) + j + 2)
			p = zeros(len(p0))
			def fplot(pij):
				p[i] = pij
				p[j] = pij
				return fint(*p)
			plot(fa, [fplot(A) for A in fa], label='Time: %.3g s' % (deltat,))
			legend()

	return par, cov

par, cov = lab.fit_generic(f, x, y, dy=dy, p0=p0)

print(cov)
print(lab.xe(par, sqrt(diag(cov))))	

par, cov = fit_bayes_1(f, x, y, dy, par, sqrt(diag(cov)))

print(cov)
print(lab.xe(par, sqrt(diag(cov))))	

show()
