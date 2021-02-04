import numpy as np
import matplotlib.pylab as plt
import healpy as hp

import lsst.sims.maf.db as db
import lsst.sims.maf.utils as utils
import lsst.sims.maf.metrics as metrics
import lsst.sims.maf.slicers as slicers
import lsst.sims.maf.stackers as stackers
import lsst.sims.maf.metricBundles as metricBundles
import lsst.sims.maf.plots as plots
from scipy.stats import binned_statistic, mode


def gap_stats(inarr, bins):
    inarr = np.sort(inarr)

    count, _b1, _b2 = binned_statistic(inarr, inarr, bins=bins, statistic=np.size)
    unight = np.unique(inarr)
    di = np.diff(unight)
    good = np.where(di < 50.)[0]
    med, _b1, _b2 = binned_statistic(unight[1:][good], di[good], bins=bins, statistic=np.median)
    un, _b1, _b2 = binned_statistic(unight[1:][good], di[good], bins=bins, statistic=np.size)

    return count, med, un


def season_breaks(in_nights, break_length=65.):
    """in_nights should be pre-sorted
    """
    di = np.diff(in_nights)
    break_indx = np.where(di > break_length)[0]
    breaks = (in_nights[break_indx] + in_nights[break_indx+1])/2.

    return breaks


def spot_inspect(filename, ra, dec, year_max=8.5, outDir='temp', season_pad=80):

    resultsDb = db.ResultsDb(outDir=outDir)

    f2c = {'u': 'purple', 'g': 'blue', 'r': 'green',
           'i': 'cyan', 'z': 'orange', 'y': 'red'}

    name = filename.replace('_v1.7_10yrs.db', '')

    conn = db.OpsimDatabase(filename)
    bundleList = []
    sql = '' #'night > 250 and night < %i' % (365*year_max)
    metric = metrics.PassMetric(['filter', 'observationStartMJD', 'fiveSigmaDepth', 'night'])
    slicer = slicers.UserPointsSlicer(ra=ra, dec=dec)
    summaryStats = []
    plotDict = {}
    bundleList.append(metricBundles.MetricBundle(metric, slicer, sql,
                                                 plotDict=plotDict,
                                                 summaryMetrics=summaryStats,
                                                 runName=name))
    bd = metricBundles.makeBundlesDictFromList(bundleList)
    bg = metricBundles.MetricBundleGroup(bd, conn, outDir=outDir, resultsDb=resultsDb)
    bg.runAll()
    #bg.plotAll(closefigs=False)
    mv = bundleList[0].metricValues[0]
    mv.sort(order='observationStartMJD')
    breaks = season_breaks(mv['night'])

    breaks = np.array([mv['night'].min()-season_pad] + breaks.tolist() + [mv['night'].max()+season_pad])

    fig = plt.figure()
    ax1 = fig.add_subplot(1, 1, 1)



    di = np.diff(breaks)
    mps = breaks[0:-1] + di/2
    counts, med_gaps, unights = gap_stats(mv['night'], bins=breaks)

    for fn in f2c:
        in_filt = np.where(mv['filter'] == fn)[0]
        ax1.plot(mv['night'][in_filt],
                 mv['fiveSigmaDepth'][in_filt], 'o',
                 color=f2c[fn], label=fn, alpha=0.5)
    ax1.set_xlabel('Night')
    ax1.set_ylabel(r'5$\sigma$ depth (mags)')

    for i in np.arange(mps.size):
        plt.annotate('%i\n %.1f \n %i' % (counts[i], med_gaps[i], unights[i]), [mps[i], 20])

    #plt.legend(loc=(1.04,0))
    for br in breaks:
        ax1.axvline(br)
    ax1.set_ylim([19.5, 25.5])
    #plt.xlim([1340, 1560])
    ax1.set_title(name+' ra=%.2f, dec=%.2f' % (ra, dec))

    return fig, ax1
