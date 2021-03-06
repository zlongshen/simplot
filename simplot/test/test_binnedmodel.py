
import itertools
import math
import random
import string
import unittest

import numpy as np

from simplot.mc.montecarlo import ToyMC
from simplot.mc.statistics import Mean, StandardDeviation, calculate_statistics_from_toymc
from simplot.mc.likelihood import EventRateLikelihood, SumLikelihood
from simplot.mc.generators import GaussianGenerator, GeneratorList
from simplot.mc.priors import GaussianPrior, CombinedPrior, OscillationParametersPrior
from simplot.binnedmodel.sample import Sample, BinnedSample, BinnedSampleWithOscillation, CombinedBinnedSample
from simplot.binnedmodel.systematics import Systematics, SplineSystematics, FluxSystematics, FluxAndSplineSystematics

################################################################################

class TestSystematics(unittest.TestCase):
    def test_systematics_exception(self):
        syst = Systematics()
        self.assertEquals(syst.spline_parameter_values, [])
        with self.assertRaises(NotImplementedError):
            syst.parameter_names
        with self.assertRaises(NotImplementedError):
            syst(None, None, None)

################################################################################

class TestModel(unittest.TestCase):

    def test_sample_exception(self):
        s = Sample(["a", "b"])
        with self.assertRaises(NotImplementedError):
            s([0.0, 0.0])

    def test_simple_model_building(self):
        #try without cache
        self._buildsimplemodel(cachestr=None)
        #try with cache
        cachestr = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(25))
        #run twice to test read and write
        model1 = self._buildsimplemodel(cachestr=cachestr)
        model2 = self._buildsimplemodel(cachestr=cachestr) # definitely loaded from disk
        #compare models
        for pars in itertools.product(range(-5, 5), repeat=2):
            x1 = model1(pars)
            x2 = model2(pars)
            for xi1, xi2 in zip(x1, x2):
                self.assertAlmostEquals(xi1, xi2)
        return

    def test_generate_mc(self):
        _, toymc, _ = self._buildmodelnoosc()
        npe = 100
        for _ in xrange(npe):
            toymc()
        return

    def test_model_building_withosc(self):
        #run twice to test caching
        cachestr = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(25))
        for _ in xrange(2):
            self._buildmodelwithosc(cachestr=cachestr)

    def test_generate_mc_withosc(self):
        _, toymc, _ = self._buildmodelwithosc()
        npe = 100
        for _ in xrange(npe):
            toymc()
        return

    def _normalise(self, arr, norm=1.0):
        return arr * (norm/np.sum(arr))

    def test_generate_mc_values(self):
        self.generate_mc_values()
        self.generate_mc_values(fixflux=True, fixxsec=True)
        self.generate_mc_values(fixflux=True)
        self.generate_mc_values(fixxsec=True)

    def generate_mc_values(self, fixflux=False, fixxsec=False):
        _, toymc, _ = self._buildmodelnoosc()
        if fixxsec and fixflux:
            toymc.generator.fixallexcept([]) # fix all parameters
        elif fixxsec:
            toymc.generator.setfixed(["signal", "bkgd"]) # fix flux errors
        elif fixflux:
            toymc.generator.fixallexcept(["signal", "bkgd"]) # fix flux errors
        mean = Mean()
        stddev = StandardDeviation()
        statistics = [mean, stddev]
        calculate_statistics_from_toymc(toymc, statistics, 1000)
        #calculate the expected mean
        binedges = np.linspace(0.0, 5.0, num=100.0) 
        x = (binedges[1:] + binedges[:-1]) / 2.0
        mu = 1.0
        sigma = 0.25
        signal = self._normalise(1.0/(sigma * np.sqrt(2 * np.pi)) * np.exp( - (x - mu)**2 / (2 * sigma**2) ), norm=0.5*10**5)
        background = self._normalise(np.ones(shape=signal.shape), norm=0.5*10**5)
        expectedmean = signal + background
        serr = 0.1
        berr = 0.1
        ferr = 0.1
        expectedvariance_flux = 8.0*np.power(ferr*0.125*(signal+background), 2)
        expectedvariance_xsec = np.power(serr*signal, 2) + np.power(berr*background, 2)
        if not any((fixflux, fixxsec)):
            expectedsigma = np.sqrt(expectedvariance_xsec + expectedvariance_flux)
        elif fixflux and fixxsec:
            expectedsigma = np.zeros(len(expectedvariance_flux))
        elif fixflux:
            expectedsigma = np.sqrt(expectedvariance_xsec)
        elif fixxsec:
            expectedsigma = np.sqrt(expectedvariance_flux)
        expectedsigma *= (mean.eval()/expectedmean) # correct sigma for stat err on mean
        #check prediction
        #import matplotlib.pyplot as plt
        #plt.errorbar(x, mean.eval(), yerr=np.sqrt(mean.eval()), color="blue")
        #plt.scatter(x, expectedmean, color="red")
        #plt.show()
        #raw_input("wait")
        for m, e, mex in itertools.izip_longest(mean.eval(), mean.err(), expectedmean):
            e = np.sqrt(e**2 + mex)
            self.assertAlmostEquals(m, mex, delta=5.0*e)
        for s, e, sex in itertools.izip_longest(stddev.eval(), stddev.err(), expectedsigma):
            self.assertAlmostEquals(s, sex, delta=5.0*e)
        return

    def _buildsimplemodel(self, cachestr=None):
        systematics = [("x", [-5.0, 0.0, 5.0]),
                       ("y", [-5.0, 0.0, 5.0])]
        systematics = SplineSystematics(systematics)
        def gen(N):
            for _ in xrange(N):
                coord = np.random.poisson(size=2)
                yield coord, 1.0, [(-4.0, 1.0, 5.0), (-4.0, 1.0, 5.0)]
        binning = [("a", np.arange(0.0, 10.0)), ("b", np.arange(0.0, 10.0))]
        observables = ["a"]
        model = BinnedSample("simplemodel", binning, observables, gen(10**4), systematics=systematics, cache_name=cachestr)
        return model

    def _buildmodelnoosc(self, cachestr="testnoosc"):
        return self._buildmodel(withosc=False, cachestr=cachestr)

    def _buildmodelwithosc(self, cachestr="testwithosc"):
        return self._buildmodel(withosc=True, cachestr=cachestr)

    def _buildmodel(self, withosc, cachestr="testnoosc"):
        #build a simple dummy model
        binning = [("reco_energy", np.linspace(0.0, 5.0, num=100.0)),
                       ("true_energy", np.linspace(0.0, 5.0, num=25.0)),
                        ("true_nupdg", [0.0, 1.0, 2.0, 3.0, 4.0]),
                        ("beammode", [0.0, 1.0, 2.0]),
        ]
        signalsyst = np.array([[-4.0, 1.0, 6.0], [1.0, 1.0, 1.0]])
        bkgdsyst = np.array([[1.0, 1.0, 1.0], [-4.0, 1.0, 6.0]])
        def gen(N):
            for _ in xrange(N):
                nupdg = np.random.randint(4)
                if np.random.uniform() > 0.5:
                    #signal
                    while True:
                        true = np.random.normal(1.0, 0.25)
                        if 0.0 <= true <= 5.0:
                            break
                    syst = signalsyst
                else:
                    #bkgd
                    true = np.random.uniform(0.0, 5.0)
                    syst = bkgdsyst
                while True:
                    reco = np.random.normal(true, 0.0001)
                    if 0.0 <= reco <= 5.0:
                        break
                beammode = np.random.randint(2)
                if beammode == 1:
                    nupdg = {0:1, 1:0, 2:3, 3:2}[nupdg]
                if reco > 0.0 and true > 0.0:
                    yield (reco, true, nupdg, beammode), 1.0, syst
        def gensk(N):
            eff = 0.5
            for (reco, true, nupdg, beammode), weight, syst in gen(N):
                   yield (reco, true, nupdg), eff*weight, weight, syst
        iternd280 = gen(10**5)
        itersuperk = gensk(1000)
        systematics = [("signal", [-5.0, 0.0, 5.0]), ("bkgd", [-5.0, 0.0, 5.0])]
        flux_error_binning = [((beamname, flavname), beambin, flavbin, [0.0, 5.0]) for beambin, beamname in enumerate(["RHC", "FHC"]) for flavbin, flavname in enumerate(["numu", "nue", "numubar", "nuebar"])]
        fluxparametermap = FluxSystematics.make_flux_parameter_map(binning[1][1], flux_error_binning)
        systematics = FluxAndSplineSystematics(systematics, enudim=1, nupdgdim=2, beammodedim=3, fluxparametermap=fluxparametermap)
        observables = ["reco_energy"]
        nd280 = BinnedSample("nd280", binning, observables, iternd280, cache_name="nd280_" + cachestr, systematics=systematics)
        xsecprior = GaussianPrior(["signal", "bkgd"], [0.0, 0.0], [0.1, 0.1], seed=1231)
        fluxprior = GaussianPrior([("f_%s_%s_0" %(beamname, flavname)) for beambin, beamname in enumerate(["RHC", "FHC"]) for flavbin, flavname in enumerate(["numu", "nue", "numubar", "nuebar"])], [1.0]*8, [0.1]*8, seed=23123)
        prior = CombinedPrior([xsecprior, fluxprior])
        if withosc:
            superk = BinnedSampleWithOscillation("superk", binning, observables, itersuperk, "true_energy", "true_nupdg", 295.0, cache_name="superk_" + cachestr)
            model = CombinedBinnedSample([nd280, superk])
            prior = CombinedPrior([prior, OscillationParametersPrior()])
        else:
            model = CombinedBinnedSample([nd280])
        #generate monte carlo
        ratevector = model
        toymc = ToyMC(ratevector, prior.generator)
        lhd_data = EventRateLikelihood(model, data=toymc.asimov().vec)
        lhd_prior = prior.likelihood
        lhd = SumLikelihood([lhd_data, lhd_prior])
        return model, toymc, lhd

################################################################################

class TestOscillationCalculation(unittest.TestCase):

    def _buildtestmc(self, cachestr=None):
        systematics = [("x", [-5.0, 0.0, 5.0]),
                       ("y", [-5.0, 0.0, 5.0]),
                       ("z", [-5.0, 0.0, 5.0]),
        ]
        systematics = SplineSystematics(systematics)
        random = np.random.RandomState(1222)
        def gen(N):
            for _ in xrange(N):
                nupdg = random.uniform(0.0, 4.0)
                trueenu = random.uniform(0.0, 5.0)
                recoenu = random.uniform(1.0, 0.1) * trueenu
                coord = (trueenu, nupdg, recoenu)
                yield coord, 1.0, 1.0, [(-4., 1.0, 6.0), (-4.0, 1.0, 6.0), (-4.0, 1.0, 6.0)]
        binning = [("trueenu", np.linspace(0.0, 5.0, num=10.0)), ("nupdg", np.arange(0.0, 5.0)), ("recoenu", np.linspace(0.0, 5.0, num=10.0))]
        observables = ["recoenu"]
        model = BinnedSampleWithOscillation("simplemodelwithoscillation", binning, observables, gen(10**4), enuaxis="trueenu", flavaxis="nupdg", 
                                            distance=295.0, systematics=systematics, probabilitycalc=None)
        oscgen = OscillationParametersPrior(seed=1225).generator
        systgen = GaussianGenerator(["x", "y", "z"], [0.0, 0.0, 0.0], [0.1, 0.1, 0.1], seed=1226)
        #toymc = ToyMC(model, GeneratorList(oscgen))
        toymc = ToyMC(model, GeneratorList(oscgen, systgen))
        return toymc

    def test_systematics(self):
        toymc = self._buildtestmc()
        asimov = toymc.asimov()
        model = toymc.ratevector
        for scale in np.linspace(0.1, 1.9, num=10):
            for ipar in xrange(3):
                pars = np.copy(asimov.pars)
                pars[ipar+6] = scale - 1.0
                vec = model(pars)
                for val, expected in itertools.izip_longest(vec, asimov.vec):
                    if expected > 0.0:
                        self.assertAlmostEqual(val / expected, scale)
        return

################################################################################

def main():
    #TestModel("test_model_building_withosc").run()
    return unittest.main()

if __name__ == "__main__":
    main()

