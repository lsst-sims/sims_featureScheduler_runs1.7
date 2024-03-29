import numpy as np
import matplotlib.pylab as plt
import healpy as hp
from lsst.sims.featureScheduler.modelObservatory import Model_observatory
from lsst.sims.featureScheduler.schedulers import Core_scheduler, simple_filter_sched
from lsst.sims.featureScheduler.utils import (standard_goals, NES_healpixels, Footprint,
                                              Footprints, ra_dec_hp_map, Step_slopes, magellanic_clouds_healpixels)
import lsst.sims.featureScheduler.basis_functions as bf
from lsst.sims.featureScheduler.surveys import (Greedy_survey, generate_dd_surveys,
                                                Blob_survey)
from lsst.sims.featureScheduler import sim_runner
import lsst.sims.featureScheduler.detailers as detailers
import sys
import subprocess
import os
import argparse
from astropy.coordinates import SkyCoord
from astropy import units as u
from lsst.utils import getPackageDir



def slice_wfd_area_quad(target_map):
    """
    Make a fancy 4-stripe target map
    """
    # Make it so things still sum to one.
    nslice = 2
    nslice2 = nslice * 2

    wfd = target_map['r'] * 0
    wfd_indices = np.where(target_map['r'] == 1)[0]
    wfd[wfd_indices] = 1
    wfd_accum = np.cumsum(wfd)
    split_wfd_indices = np.floor(np.max(wfd_accum)/nslice2*(np.arange(nslice2)+1)).astype(int)
    split_wfd_indices = split_wfd_indices.tolist()
    split_wfd_indices = [0] + split_wfd_indices

    return split_wfd_indices


def slice_wfd_area(nslice, target_map, scale_down_factor=0.2):
    """
    Slice the WFD area into even dec bands
    """
    # Make it so things still sum to one.
    scale_up_factor = nslice - scale_down_factor*(nslice-1)

    wfd = target_map['r'] * 0
    wfd_indices = np.where(target_map['r'] == 1)[0]
    wfd[wfd_indices] = 1
    wfd_accum = np.cumsum(wfd)
    split_wfd_indices = np.floor(np.max(wfd_accum)/nslice*(np.arange(nslice)+1)).astype(int)
    split_wfd_indices = split_wfd_indices.tolist()
    split_wfd_indices = [0] + split_wfd_indices

    all_scaled_down = {}
    for filtername in target_map:
        all_scaled_down[filtername] = target_map[filtername]+0
        all_scaled_down[filtername][wfd_indices] *= scale_down_factor

    scaled_maps = []
    for i in range(len(split_wfd_indices)-1):
        new_map = {}
        indices = wfd_indices[split_wfd_indices[i]:split_wfd_indices[i+1]]
        for filtername in all_scaled_down:
            new_map[filtername] = all_scaled_down[filtername] + 0
            new_map[filtername][indices] = target_map[filtername][indices]*scale_up_factor
        scaled_maps.append(new_map)

    return scaled_maps


def wfd_half(target_map=None):
    """return Two maps that split the WFD in two dec bands
    """
    if target_map is None:
        sg = combo_dust_fp()
        target_map = sg['r'] + 0
    wfd_pix = np.where(target_map == 1)[0]
    wfd_map = target_map*0
    wfd_map[wfd_pix] = 1
    wfd_halves = slice_wfd_area(2, {'r': wfd_map}, scale_down_factor=0)
    result = [-wfd_halves[0]['r'], -wfd_halves[1]['r']]
    return result


def gen_greedy_surveys(nside=32, footprints=None,
                       nexp=1, exptime=30., filters=['r', 'i', 'z', 'y'],
                       camera_rot_limits=[-80., 80.],
                       shadow_minutes=60., max_alt=76., moon_distance=30., ignore_obs='DD',
                       m5_weight=6., footprint_weight=0.6, slewtime_weight=3.,
                       stayfilter_weight=3., roll_weight=3.):
    """
    Make a quick set of greedy surveys

    This is a convienence function to generate a list of survey objects that can be used with
    lsst.sims.featureScheduler.schedulers.Core_scheduler.
    To ensure we are robust against changes in the sims_featureScheduler codebase, all kwargs are
    explicitly set.

    Parameters
    ----------
    nside : int (32)
        The HEALpix nside to use
    nexp : int (1)
        The number of exposures to use in a visit.
    exptime : float (30.)
        The exposure time to use per visit (seconds)
    filters : list of str (['r', 'i', 'z', 'y'])
        Which filters to generate surveys for.
    camera_rot_limits : list of float ([-87., 87.])
        The limits to impose when rotationally dithering the camera (degrees).
    shadow_minutes : float (60.)
        Used to mask regions around zenith (minutes)
    max_alt : float (76.
        The maximium altitude to use when masking zenith (degrees)
    moon_distance : float (30.)
        The mask radius to apply around the moon (degrees)
    ignore_obs : str or list of str ('DD')
        Ignore observations by surveys that include the given substring(s).
    m5_weight : float (3.)
        The weight for the 5-sigma depth difference basis function
    footprint_weight : float (0.3)
        The weight on the survey footprint basis function.
    slewtime_weight : float (3.)
        The weight on the slewtime basis function
    stayfilter_weight : float (3.)
        The weight on basis function that tries to stay avoid filter changes.
    """
    # Define the extra parameters that are used in the greedy survey. I
    # think these are fairly set, so no need to promote to utility func kwargs
    greed_survey_params = {'block_size': 1, 'smoothing_kernel': None,
                           'seed': 42, 'camera': 'LSST', 'dither': True,
                           'survey_name': 'greedy'}

    surveys = []
    detailer = detailers.Camera_rot_detailer(min_rot=np.min(camera_rot_limits), max_rot=np.max(camera_rot_limits))
    wfd_halves = wfd_half()
    for filtername in filters:
        bfs = []
        bfs.append((bf.M5_diff_basis_function(filtername=filtername, nside=nside), m5_weight))
        bfs.append((bf.Footprint_basis_function(filtername=filtername,
                                                footprint=footprints,
                                                out_of_bounds_val=np.nan, nside=nside), footprint_weight))
        bfs.append((bf.Slewtime_basis_function(filtername=filtername, nside=nside), slewtime_weight))
        bfs.append((bf.Strict_filter_basis_function(filtername=filtername), stayfilter_weight))
        bfs.append((bf.Map_modulo_basis_function(wfd_halves), roll_weight))
        # Masks, give these 0 weight
        bfs.append((bf.Zenith_shadow_mask_basis_function(nside=nside, shadow_minutes=shadow_minutes,
                                                         max_alt=max_alt), 0))
        bfs.append((bf.Moon_avoidance_basis_function(nside=nside, moon_distance=moon_distance), 0))

        bfs.append((bf.Filter_loaded_basis_function(filternames=filtername), 0))
        bfs.append((bf.Planet_mask_basis_function(nside=nside), 0))

        weights = [val[1] for val in bfs]
        basis_functions = [val[0] for val in bfs]
        surveys.append(Greedy_survey(basis_functions, weights, exptime=exptime, filtername=filtername,
                                     nside=nside, ignore_obs=ignore_obs, nexp=nexp,
                                     detailers=[detailer], **greed_survey_params))

    return surveys


def generate_blobs(nside, nexp=1, footprints=None,
                   exptime=30., filter1s=['u', 'u', 'g', 'r', 'i', 'z', 'y'],
                   filter2s=['g', 'r', 'r', 'i', 'z', 'y', 'y'], pair_time=22.,
                   camera_rot_limits=[-80., 80.], n_obs_template=3,
                   season=300., season_start_hour=-4., season_end_hour=2.,
                   shadow_minutes=60., max_alt=76., moon_distance=30., ignore_obs='DD',
                   m5_weight=6., footprint_weight=0.6, slewtime_weight=3.,
                   stayfilter_weight=3., template_weight=12., roll_weight=3.):
    """
    Generate surveys that take observations in blobs.

    Parameters
    ----------
    nside : int (32)
        The HEALpix nside to use
    nexp : int (1)
        The number of exposures to use in a visit.
    exptime : float (30.)
        The exposure time to use per visit (seconds)
    filter1s : list of str
        The filternames for the first set
    filter2s : list of str
        The filter names for the second in the pair (None if unpaired)
    pair_time : float (22)
        The ideal time between pairs (minutes)
    camera_rot_limits : list of float ([-80., 80.])
        The limits to impose when rotationally dithering the camera (degrees).
    n_obs_template : int (3)
        The number of observations to take every season in each filter
    season : float (300)
        The length of season (i.e., how long before templates expire) (days)
    season_start_hour : float (-4.)
        For weighting how strongly a template image needs to be observed (hours)
    sesason_end_hour : float (2.)
        For weighting how strongly a template image needs to be observed (hours)
    shadow_minutes : float (60.)
        Used to mask regions around zenith (minutes)
    max_alt : float (76.
        The maximium altitude to use when masking zenith (degrees)
    moon_distance : float (30.)
        The mask radius to apply around the moon (degrees)
    ignore_obs : str or list of str ('DD')
        Ignore observations by surveys that include the given substring(s).
    m5_weight : float (3.)
        The weight for the 5-sigma depth difference basis function
    footprint_weight : float (0.3)
        The weight on the survey footprint basis function.
    slewtime_weight : float (3.)
        The weight on the slewtime basis function
    stayfilter_weight : float (3.)
        The weight on basis function that tries to stay avoid filter changes.
    template_weight : float (12.)
        The weight to place on getting image templates every season
    """

    blob_survey_params = {'slew_approx': 7.5, 'filter_change_approx': 140.,
                          'read_approx': 2., 'min_pair_time': 15., 'search_radius': 30.,
                          'alt_max': 85., 'az_range': 90., 'flush_time': 30.,
                          'smoothing_kernel': None, 'nside': nside, 'seed': 42, 'dither': True,
                          'twilight_scale': True}

    surveys = []
    wfd_halves = wfd_half()
    times_needed = [pair_time, pair_time*2]
    for filtername, filtername2 in zip(filter1s, filter2s):
        detailer_list = []
        detailer_list.append(detailers.Camera_rot_detailer(min_rot=np.min(camera_rot_limits),
                                                           max_rot=np.max(camera_rot_limits)))
        detailer_list.append(detailers.Close_alt_detailer())
        # List to hold tuples of (basis_function_object, weight)
        bfs = []

        if filtername2 is not None:
            bfs.append((bf.M5_diff_basis_function(filtername=filtername, nside=nside), m5_weight/2.))
            bfs.append((bf.M5_diff_basis_function(filtername=filtername2, nside=nside), m5_weight/2.))

        else:
            bfs.append((bf.M5_diff_basis_function(filtername=filtername, nside=nside), m5_weight))

        if filtername2 is not None:
            bfs.append((bf.Footprint_basis_function(filtername=filtername,
                                                    footprint=footprints,
                                                    out_of_bounds_val=np.nan, nside=nside), footprint_weight/2.))
            bfs.append((bf.Footprint_basis_function(filtername=filtername2,
                                                    footprint=footprints,
                                                    out_of_bounds_val=np.nan, nside=nside), footprint_weight/2.))
        else:
            bfs.append((bf.Footprint_basis_function(filtername=filtername,
                                                    footprint=footprints, out_of_bounds_val=np.nan,
                                                    nside=nside,), footprint_weight))

        bfs.append((bf.Slewtime_basis_function(filtername=filtername, nside=nside), slewtime_weight))
        bfs.append((bf.Strict_filter_basis_function(filtername=filtername), stayfilter_weight))

        if filtername2 is not None:
            bfs.append((bf.N_obs_per_year_basis_function(filtername=filtername, nside=nside,
                                                         footprint=footprints.get_footprint(filtername),
                                                         n_obs=n_obs_template, season=season,
                                                         season_start_hour=season_start_hour,
                                                         season_end_hour=season_end_hour), template_weight/2.))
            bfs.append((bf.N_obs_per_year_basis_function(filtername=filtername2, nside=nside,
                                                         footprint=footprints.get_footprint(filtername2),
                                                         n_obs=n_obs_template, season=season,
                                                         season_start_hour=season_start_hour,
                                                         season_end_hour=season_end_hour), template_weight/2.))
        else:
            bfs.append((bf.N_obs_per_year_basis_function(filtername=filtername, nside=nside,
                                                         footprint=footprints.get_footprint(filtername),
                                                         n_obs=n_obs_template, season=season,
                                                         season_start_hour=season_start_hour,
                                                         season_end_hour=season_end_hour), template_weight))
        bfs.append((bf.Map_modulo_basis_function(wfd_halves), roll_weight))
        # Masks, give these 0 weight
        bfs.append((bf.Zenith_shadow_mask_basis_function(nside=nside, shadow_minutes=shadow_minutes, max_alt=max_alt,
                                                         penalty=np.nan, site='LSST'), 0.))
        bfs.append((bf.Moon_avoidance_basis_function(nside=nside, moon_distance=moon_distance), 0.))
        filternames = [fn for fn in [filtername, filtername2] if fn is not None]
        bfs.append((bf.Filter_loaded_basis_function(filternames=filternames), 0))
        if filtername2 is None:
            time_needed = times_needed[0]
        else:
            time_needed = times_needed[1]
        bfs.append((bf.Time_to_twilight_basis_function(time_needed=time_needed), 0.))
        bfs.append((bf.Not_twilight_basis_function(), 0.))
        bfs.append((bf.Planet_mask_basis_function(nside=nside), 0.))

        # unpack the basis functions and weights
        weights = [val[1] for val in bfs]
        basis_functions = [val[0] for val in bfs]
        if filtername2 is None:
            survey_name = 'blob, %s' % filtername
        else:
            survey_name = 'blob, %s%s' % (filtername, filtername2)
        if filtername2 is not None:
            detailer_list.append(detailers.Take_as_pairs_detailer(filtername=filtername2))
        surveys.append(Blob_survey(basis_functions, weights, filtername1=filtername, filtername2=filtername2,
                                   exptime=exptime,
                                   ideal_pair_time=pair_time,
                                   survey_note=survey_name, ignore_obs=ignore_obs,
                                   nexp=nexp, detailers=detailer_list, **blob_survey_params))

    return surveys


def run_sched(surveys, survey_length=365.25, nside=32, fileroot='baseline_', verbose=False,
              extra_info=None, illum_limit=40.):
    years = np.round(survey_length/365.25)
    scheduler = Core_scheduler(surveys, nside=nside)
    n_visit_limit = None
    filter_sched = simple_filter_sched(illum_limit=illum_limit)
    observatory = Model_observatory(nside=nside)
    observatory, scheduler, observations = sim_runner(observatory, scheduler,
                                                      survey_length=survey_length,
                                                      filename=fileroot+'%iyrs.db' % years,
                                                      delete_past=True, n_visit_limit=n_visit_limit,
                                                      verbose=verbose, extra_info=extra_info,
                                                      filter_scheduler=filter_sched)


def make_rolling_footprints(mjd_start=59853.5, sun_RA_start=3.27717639, nslice=2, scale=0.8, nside=32):
    hp_footprints = combo_dust_fp(nside=nside)

    down = 1.-scale
    up = nslice - down*(nslice-1)
    start = [1., 1., 1.]
    end = [1., 1., 1., 1., 1., 1.]
    if nslice == 2:
        rolling = [up, down, up, down, up, down]
    elif nslice == 3:
        rolling = [up, down, down, up, down, down]
    elif nslice == 6:
        rolling = [up, down, down, down, down, down]
    all_slopes = [start + np.roll(rolling, i).tolist()+end for i in range(nslice)]

    fp_non_wfd = Footprint(mjd_start, sun_RA_start=sun_RA_start)
    rolling_footprints = []
    for i in range(nslice):
        step_func = Step_slopes(rise=all_slopes[i])
        rolling_footprints.append(Footprint(mjd_start, sun_RA_start=sun_RA_start,
                                            step_func=step_func))

    split_wfd_indices = slice_wfd_area_quad(hp_footprints)
    wfd = hp_footprints['r'] * 0
    wfd_indx = np.where(hp_footprints['r'] == 1)[0]
    non_wfd_indx = np.where(hp_footprints['r'] != 1)[0]
    wfd[wfd_indx] = 1
    for key in hp_footprints:
        temp = hp_footprints[key] + 0
        temp[wfd_indx] = 0
        fp_non_wfd.set_footprint(key, temp)

        for i in range(2):
            temp = hp_footprints[key] + 0
            temp[non_wfd_indx] = 0
            indx = wfd_indx[split_wfd_indices[i]:split_wfd_indices[i+1]]
            temp[indx] = 0
            indx = wfd_indx[split_wfd_indices[i+2]:split_wfd_indices[i+3]]
            temp[indx] = 0
            rolling_footprints[i].set_footprint(key, temp)

    result = Footprints([fp_non_wfd] + rolling_footprints)
    return result


def combo_dust_fp(nside=32,
                  wfd_weights={'u': 0.31, 'g': 0.44, 'r': 1., 'i': 1., 'z': 0.9, 'y': 0.9},
                  wfd_dust_weights={'u': 0.13, 'g': 0.13, 'r': 0.25, 'i': 0.25, 'z': 0.25, 'y': 0.25},
                  nes_dist_eclip_n=10., nes_dist_eclip_s=-30., nes_south_limit=-5, ses_dist_eclip=10.,
                  nes_weights={'u': 0, 'g': 0.2, 'r': 0.46, 'i': 0.46, 'z': 0.4, 'y': 0},
                  dust_limit=0.19,
                  wfd_north_dec=7.8, wfd_south_dec=-70.2,
                  mc_wfd=True,
                  outer_bridge_l=240, outer_bridge_width=10., outer_bridge_alt=13.,
                  bulge_lon_span=20., bulge_alt_span=10.,
                  north_weights={'g': 0.03, 'r': 0.03, 'i': 0.03}, north_limit=30.):
    """
    """
    # Telecope is at latitude of -30.23


    ebvDataDir = getPackageDir('sims_maps')
    filename = 'DustMaps/dust_nside_%i.npz' % nside
    dustmap = np.load(os.path.join(ebvDataDir, filename))['ebvMap']

    # wfd covers -72.25 < dec < 12.4. Avoid galactic plane |b| > 15 deg
    wfd_north = wfd_north_dec
    wfd_south = wfd_south_dec

    ra, dec = np.degrees(ra_dec_hp_map(nside=nside))
    WFD_no_dust = np.zeros(ra.size)
    WFD_dust = np.zeros(ra.size)

    coord = SkyCoord(ra=ra*u.deg, dec=dec*u.deg)
    gal_lon, gal_lat = coord.galactic.l.deg, coord.galactic.b.deg

    # let's make a first pass here
    WFD_no_dust[np.where((dec > wfd_south) &
                         (dec < wfd_north) &
                         (dustmap < dust_limit))] = 1.

    WFD_dust[np.where((dec > wfd_south) &
                      (dec < wfd_north) &
                      (dustmap > dust_limit))] = 1.
    WFD_dust[np.where(dec < wfd_south)] = 1.

    # Fill in values for WFD and WFD_dusty
    result = {}
    for key in wfd_weights:
        result[key] = WFD_no_dust + 0.
        result[key][np.where(result[key] == 1)] = wfd_weights[key]
        result[key][np.where(WFD_dust == 1)] = wfd_dust_weights[key]

    coord = SkyCoord(ra=ra*u.deg, dec=dec*u.deg)
    eclip_lat = coord.barycentrictrueecliptic.lat.deg

    # Any part of the NES that is too low gets pumped up
    nes_indx = np.where(((eclip_lat < nes_dist_eclip_n) & (eclip_lat > nes_dist_eclip_s))
                        & (dec > nes_south_limit))
    nes_hp_map = ra*0
    nes_hp_map[nes_indx] = 1
    for key in result:
        result[key][np.where((nes_hp_map > 0) & (result[key] < nes_weights[key]))] = nes_weights[key]

    if mc_wfd:
        mag_clouds = magellanic_clouds_healpixels(nside)
        mag_clouds_indx = np.where(mag_clouds > 0)[0]
    else:
        mag_clouds_indx = []
    for key in result:
        result[key][mag_clouds_indx] = wfd_weights[key]

    # Put in an outer disk bridge
    outer_disk = np.where((gal_lon < (outer_bridge_l + outer_bridge_width))
                          & (gal_lon > (outer_bridge_l-outer_bridge_width))
                          & (np.abs(gal_lat) < outer_bridge_alt))
    for key in result:
        result[key][outer_disk] = wfd_weights[key]

    # Make a bulge go WFD
    bulge_pix = np.where(((gal_lon > (360-bulge_lon_span)) | (gal_lon < bulge_lon_span)) &
                         (np.abs(gal_lat) < bulge_alt_span))
    for key in result:
        result[key][bulge_pix] = wfd_weights[key]

    # Set South ecliptic to the WFD values
    ses_indx = np.where((np.abs(eclip_lat) < ses_dist_eclip) & (dec < nes_south_limit))
    for key in result:
        result[key][ses_indx] = wfd_weights[key]

    # Let's paint all the north as non-zero
    for key in north_weights:
        north = np.where((dec < north_limit) & (result[key] == 0))
        result[key][north] = north_weights[key]

    return result


def footprint_maker(fpid):

    fps = []
    # 0 Defaults
    fps.append(combo_dust_fp())
    # 1 No northern stripe
    fps.append(combo_dust_fp(north_weights={}))
    # 2 No north, bring in the WFD a bit. wfd_north_dec=7.8, wfd_south_dec=-70.2,
    fps.append(combo_dust_fp(north_weights={},
                             wfd_north_dec=8., wfd_south_dec=-67.4))
    # 3 No north, bring in the WFD a bit. Old footprint is -62.5 to 3.6, extend bridge south
    fps.append(combo_dust_fp(north_weights={},
                             wfd_north_dec=8., wfd_south_dec=-67.4,
                             outer_bridge_l=240, outer_bridge_width=20., outer_bridge_alt=13.))

    # 4 No north, bring WFD all the way down
    fps.append(combo_dust_fp(north_weights={},
                             wfd_north_dec=3.6, wfd_south_dec=-62.5,
                             outer_bridge_l=255, outer_bridge_width=33., outer_bridge_alt=30))

    # 5 and with bigger bridge
    fps.append(combo_dust_fp(north_weights={},
                             wfd_north_dec=8., wfd_south_dec=-67.4,
                             outer_bridge_l=240, outer_bridge_width=20., outer_bridge_alt=13.))

    # 6 
    fps.append(combo_dust_fp(north_weights={},
                             wfd_north_dec=8., wfd_south_dec=-67.4,
                             outer_bridge_l=260, outer_bridge_width=20., outer_bridge_alt=13.))
    # 7 no north, no SES
    fps.append(combo_dust_fp(north_weights={}, ses_dist_eclip=0.))

    # 8 heavy exgal
    fps.append(combo_dust_fp(north_weights={}, ses_dist_eclip=0., outer_bridge_width=0,
                             bulge_lon_span=0., bulge_alt_span=0., mc_wfd=False,
                             wfd_north_dec=12.5, wfd_south_dec=-70.4))


    return fps[fpid]


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)
    parser.add_argument("--survey_length", type=float, default=365.25*10)
    parser.add_argument("--outDir", type=str, default="")
    parser.add_argument("--maxDither", type=float, default=0.7, help="Dither size for DDFs (deg)")
    parser.add_argument("--nslice", type=int, default=2)
    parser.add_argument("--scale", type=float, default=0.8)
    parser.add_argument("--nexp", type=int, default=2)
    parser.add_argument("--fpid", type=int, default=0)

    args = parser.parse_args()
    survey_length = args.survey_length  # Days
    outDir = args.outDir
    verbose = args.verbose
    max_dither = args.maxDither
    scale = args.scale
    nslice = args.nslice
    nexp = args.nexp
    fpid = args.fpid

    nside = 32
    per_night = True  # Dither DDF per night
    mixed_pairs = True  # For the blob scheduler
    camera_ddf_rot_limit = 75.

    extra_info = {}
    exec_command = ''
    for arg in sys.argv:
        exec_command += ' ' + arg
    extra_info['exec command'] = exec_command
    try:
        extra_info['git hash'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
    except subprocess.CalledProcessError:
        extra_info['git hash'] = 'Not in git repo'

    extra_info['file executed'] = os.path.realpath(__file__)

    fileroot = 'footprint_%i_' % fpid

    file_end = 'v1.7.1'

    # Mark position of the sun at the start of the survey. Usefull for rolling cadence.
    observatory = Model_observatory(nside=nside)
    conditions = observatory.return_conditions()
    sun_ra_0 = conditions.sunRA  # radians

    # Set up the DDF surveys to dither
    dither_detailer = detailers.Dither_detailer(per_night=per_night, max_dither=max_dither)
    details = [detailers.Camera_rot_detailer(min_rot=-camera_ddf_rot_limit, max_rot=camera_ddf_rot_limit), dither_detailer]
    ddfs = generate_dd_surveys(nside=nside, nexp=nexp, detailers=details)

    # Set up rolling maps
    #footprints = make_rolling_footprints(mjd_start=conditions.mjd_start,
    #                                     sun_RA_start=conditions.sun_RA_start, nslice=nslice, scale=scale,
    #                                     nside=nside)
    fp_hp = footprint_maker(fpid)
    # In case we want to flag the wfd pixels later
    wfd_hp = np.where(fp_hp['r'] == 1)[0]
    footprints = Footprint(conditions.mjd_start, sun_RA_start=conditions.sun_RA_start, nside=nside)
    for i, key in enumerate(fp_hp):
        footprints.footprints[i, :] = fp_hp[key]

    greedy = gen_greedy_surveys(nside, nexp=nexp, footprints=footprints)
    blobs = generate_blobs(nside, nexp=nexp, footprints=footprints)
    surveys = [ddfs, blobs, greedy]
    run_sched(surveys, survey_length=survey_length, verbose=verbose,
              fileroot=os.path.join(outDir, fileroot+file_end), extra_info=extra_info,
              nside=nside)
