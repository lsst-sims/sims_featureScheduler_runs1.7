import numpy as np
import matplotlib.pylab as plt
import healpy as hp
from lsst.sims.featureScheduler.modelObservatory import Model_observatory
from lsst.sims.featureScheduler.schedulers import Core_scheduler, simple_filter_sched
from lsst.sims.featureScheduler.utils import standard_goals, generate_goal_map, Footprint, empty_observation
import lsst.sims.featureScheduler.basis_functions as bf
from lsst.sims.featureScheduler.surveys import (Greedy_survey, generate_dd_surveys,
                                                Blob_survey)
from lsst.sims.featureScheduler import sim_runner
import lsst.sims.featureScheduler.detailers as detailers
import sys
import subprocess
import os
import argparse
import copy
from lsst.sims.featureScheduler.surveys import BaseSurvey
from lsst.sims.almanac import Almanac
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.time import Time
from lsst.sims.downtimeModel import ScheduledDowntimeData
from scipy.interpolate import interp1d
from lsst.sims.utils import Site, _approx_RaDec2AltAz
from astroplan import FixedTarget, Observer
import astropy.units as u


def gen_carina_sequence(ra=161.264583, dec=-59.68445833, survey_name='carina',
                        sequence='griu', nvis=[1, 1, 1, 1],
                        exptime=30., u_exptime=30., nexp=2, u_nexp=2):
    """Generate a list of times to observe Carina
    """
    # XXX--temp
    # ra = 300.

    ra = np.radians(ra)
    dec = np.radians(dec)

    observations = []
    for num, filtername in zip(nvis, sequence):
        # XXX--in theory, we could use decimal nvis and do a random number draw here, so
        # nvis=2.5 means 2 half the time and 3 half the time.
        for j in range(num):
            obs = empty_observation()
            obs['filter'] = filtername
            if filtername == 'u':
                obs['exptime'] = u_exptime
                obs['nexp'] = u_nexp
            else:
                obs['exptime'] = exptime
                obs['nexp'] = nexp
            obs['RA'] = ra
            obs['dec'] = dec
            obs['note'] = survey_name
            obs['rotTelPos'] = 0.  # XXX--a brief check here
            observations.append(obs)
    return {'carina': np.array(observations)}


def pick_times(mjd_start=59853.5, moon_limit=35, run_length=7):
    """Need to pick times
    """
    # want 7 consecutive days where carina is visible most of the night
    # the moon is < 40% illuminated
    # there is no scheduled downtime

    mjd_start_time = Time(mjd_start, format='mjd')

    site = Site('LSST')
    location = EarthLocation(lat=site.latitude, lon=site.longitude,
                             height=site.height)
    rubin = Observer(location=location)
    sched_downtime_data = ScheduledDowntimeData(mjd_start_time)
    sched_downtimes = sched_downtime_data()

    down_starts = []
    down_ends = []
    for dt in sched_downtimes:
        down_starts.append(dt['start'].mjd)
        down_ends.append(dt['end'].mjd)
    downtimes = np.array(list(zip(down_starts, down_ends)), dtype=list(zip(['start', 'end'], [float, float])))
    downtimes.sort(order='start')

    almanac = Almanac(mjd_start=mjd_start)
    moon_phases = interp1d(almanac.sun_moon['mjd'], almanac.sun_moon['moon_phase'])(almanac.sunsets['sun_n18_setting'])

    possible_nights = np.ones(moon_phases.size)
    possible_nights[np.where(moon_phases > moon_limit)] = 0

    # block out anything too early
    possible_nights[np.where(almanac.sunsets['sun_n18_setting'] < mjd_start)] = 0

    # do a loop to block out all the nights between downtime start and end
    for dt in downtimes:
        indx1 = almanac.mjd_indx(dt['start'])
        indx2 = almanac.mjd_indx(dt['end'])
        possible_nights[indx1:indx2+1] = 0

    # XXX----mark out nights where the target is not up long enough.
    # Maybe has to be 2 hours before sunset and 2 hours before sunrise?
    good = np.where(possible_nights > 0)[0]
    carina_coord = SkyCoord(ra=161.264583*u.deg, dec=-59.68445833*u.deg)
    times = Time(almanac.sunsets['sun_n18_setting'][good], format='mjd')
    carina = FixedTarget(coord=carina_coord, name="Carina")
    transit_times = rubin.target_meridian_transit_time(times, carina, n_grid_points=10)
    diff1 = transit_times.mjd - almanac.sunsets['sun_n18_setting'][good]
    diff2 = almanac.sunsets['sun_n18_rising'][good] - transit_times.mjd
    delta = 2./24.
    bts = np.where((diff1 < delta) | (diff2 < delta))[0]

    possible_nights[good[bts]] = 0

    counter = 0
    running_count = np.zeros(possible_nights.size)
    for i, val in enumerate(possible_nights[0:-1]):
        running_count[i] += counter
        if val > 0:
            counter += 1
        else:
            counter = 0
    
    possible_ends = np.where(running_count >= run_length)[0]

    for i in range(0, run_length):
        possible_nights[possible_ends-i] += 1
    possible_nights[np.where(possible_nights <= 1)] = 0
    possible_nights[np.where(possible_nights > 1)] = 1

    mjd_starts = []
    for i in range(10):
        start_indx = np.min(np.where(possible_nights > 0)[0])
        mjd_starts.extend(almanac.sunsets['sun_n18_setting'][start_indx:start_indx+run_length].tolist())
        # no to block out days near there
        mask = np.where(almanac.sunsets['sun_n18_setting'] < (np.max(mjd_starts)+340))[0]
        possible_nights[mask] = 0

    print(mjd_starts)

def gen_carina_times():
    """Let's figure out when we want to launch these things.
    """

    # List of MJDs to start on. 
    # XXX--temp
    mjds = [59992.03798772348, 59993.03717235476, 59994.03634883789, 59995.03551756684, 
    59996.0346789225, 59997.03383325506, 59998.03298097197, 60347.04577312805, 60348.04506823188, 
    60349.044350427575, 60350.04362015519, 60351.04287783196, 60352.04212389188, 60353.041358765215,
    60731.03080681572, 60732.0299360645, 60733.02906059101, 60734.02818073612, 60735.02729685325, 
    60736.026409286074, 60737.025518379174, 61084.04094713647, 61085.04016599804, 61086.03937504534, 
    61087.03857469326, 61088.03776538372, 61089.03694753628, 61090.036121559795, 61439.04827445885, 
    61440.04762212513, 61441.046955060214, 61442.04627373023, 61443.04557859991, 61444.04487013258, 
    61445.04414878599, 61822.034851515666, 61823.0340069863, 61824.03315593768, 61825.03229877073, 
    61826.03143587429, 61827.03056854941, 61828.02969670808, 62177.043024341576, 62178.04227262642, 
    62179.041509832256, 62180.04073640052, 62181.03995276522, 62182.03915935382, 62183.03835657565, 
    62534.04873317061, 62535.048092107754, 62536.04743590718, 62537.046765011735, 62538.046079882886, 
    62539.045380986296, 62540.04466879275, 62915.03711327491, 62916.03628921276, 62917.03545752028, 
    62918.03461858956, 62919.0337727773, 62920.032920483965, 62921.032062082086, 63270.04501105705, 
    63271.04429272283, 63272.04356206162, 63273.042819500435, 63274.04206547048, 63275.041300386656, 
    63276.04052466573]
    full_list = []
    step = 30./60/24.  # to days
    n = 22  # try for this many
    delta = 30./60/24.  # Padding to try for

    for mjd in mjds:
        temp = np.arange(n)*step + mjd
        full_list.extend(temp.tolist())

    full_list = np.array(full_list)

    names = ['mjd_start', 'mjd_end', 'label']
    types = [float, float, '|U20']
    result = np.zeros(len(full_list), dtype=list(zip(names, types)))
    result['label'] = 'carina'
    result['mjd_start'] = full_list
    result['mjd_end'] = full_list + delta

    return result


class Scheduled_ddfs(BaseSurvey):
    """
    Parameters
    ----------
    times_array : np.array
        An array with columns "mjd_start", "mjd_end", and 'label' which are the alowed starting and
        ending times of the sequence
    flush_time : float (40)
        The time to allow to pass before flushing observation from queue (minutes)
    read_time : float (2.)
        The estimated read time of the camera (seconds)
    """
    def __init__(self, times_array, sequence_dict, ha_dict, basis_functions=[],
                 detailers=[], ignore_obs=None, reward_value=100, flush_time=20.,
                 read_time=2.):

        super(Scheduled_ddfs, self).__init__(basis_functions=basis_functions,
                                             detailers=detailers, ignore_obs=ignore_obs)

        self.times_array = times_array
        self.sequence_dict = sequence_dict
        self.flush_time = flush_time/60./24.
        self.observation_complete = np.zeros(self.times_array.size, dtype=bool)
        self.reward_value = reward_value
        self.ha_dict = ha_dict
        self.read_time = read_time/3600./24.

        # Add this so it will box out other observations
        self.scheduled_obs = (times_array['mjd_start'] + times_array['mjd_end'])/2.

    def _check_feasibility(self, conditions):
        result = False
        # Check if there is a sequence that wants to go
        # XXX--can probably use searchsorted here for faster results
        in_mjd = np.where((conditions.mjd > self.times_array['mjd_start']) &
                          (conditions.mjd < self.times_array['mjd_end']) &
                          (self.observation_complete == False))[0]
        for indx in in_mjd:
            ra = self.sequence_dict[self.times_array[indx]['label']]['RA'][0]
            # HA
            target_HA = (conditions.lmst - ra*12/np.pi) % 24
            in_HA_range = False


            for ha_range in self.ha_dict[self.times_array[indx]['label']]:
                lres = np.min(ha_range) <= target_HA < np.max(ha_range)
                in_HA_range = in_HA_range | lres

            if in_HA_range:
                result = True
                self.observations = copy.deepcopy(self.sequence_dict[self.times_array[indx]['label']])
                self.indx = indx
                return result

        return result

    def calc_reward_function(self, conditions):
        result = -np.inf
        if self._check_feasibility(conditions):
            result = self.reward_value
        return result

    def generate_observations_rough(self, conditions):
        result = []
        if self._check_feasibility(conditions):
            result = self.observations

            # Set the flush_by
            result['flush_by_mjd'] = conditions.mjd + self.flush_time

            # remove filters that are not mounted
            mask = np.isin(result['filter'], conditions.mounted_filters)
            result = result[mask]
            # Put current loaded filter first
            ind1 = np.where(result['filter'] == conditions.current_filter)[0]
            ind2 = np.where(result['filter'] != conditions.current_filter)[0]
            result = result[ind1.tolist() + (ind2.tolist())]

            # Set the flush_by
            # XXX--might need to add some filter change time in here
            running_time = np.cumsum(result['exptime'])/3600./24. + np.cumsum(np.ones(np.size(result))*self.read_time*result['nexp'])
            result['flush_by_mjd'] = conditions.mjd + self.flush_time + running_time

            # convert to list of array. Arglebargle, don't understand why I need a reshape there
            final_result = [row.reshape(1,) for row in result]
            result = final_result

            self.observation_complete[self.indx] = True

        return result



def gen_greedy_surveys(nside=32, nexp=2, exptime=30., filters=['r', 'i', 'z', 'y'],
                       camera_rot_limits=[-80., 80.],
                       shadow_minutes=60., max_alt=76., moon_distance=30., ignore_obs='DD',
                       m5_weight=3., footprint_weight=0.3, slewtime_weight=3.,
                       stayfilter_weight=3., footprints=None):
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
    camera_rot_limits : list of float ([-80., 80.])
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

    for filtername in filters:
        bfs = []
        bfs.append((bf.M5_diff_basis_function(filtername=filtername, nside=nside), m5_weight))
        bfs.append((bf.Footprint_basis_function(filtername=filtername,
                                                footprint=footprints,
                                                out_of_bounds_val=np.nan, nside=nside), footprint_weight))
        bfs.append((bf.Slewtime_basis_function(filtername=filtername, nside=nside), slewtime_weight))
        bfs.append((bf.Strict_filter_basis_function(filtername=filtername), stayfilter_weight))
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


def generate_blobs(nside, nexp=2, exptime=30., filter1s=['u', 'u', 'g', 'r', 'i', 'z', 'y'],
                   filter2s=['g', 'r', 'r', 'i', 'z', 'y', 'y'], pair_time=22.,
                   camera_rot_limits=[-80., 80.], n_obs_template=3,
                   season=300., season_start_hour=-4., season_end_hour=2.,
                   shadow_minutes=60., max_alt=76., moon_distance=30., ignore_obs='DD',
                   m5_weight=6., footprint_weight=0.6, slewtime_weight=3.,
                   stayfilter_weight=3., template_weight=12., footprints=None):
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
                                                    footprint=footprints,
                                                    out_of_bounds_val=np.nan, nside=nside), footprint_weight))

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
        bfs.append((bf.Time_to_scheduled_basis_function(time_needed=time_needed), 0))

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


def nes_light_footprints(nside=None):
    """
    A quick function to generate the "standard" goal maps. This is the traditional WFD/mini survey footprint.
    """

    NES_scaledown = 2.
    SCP_scaledown = 1.5

    result = {}
    result['u'] = generate_goal_map(nside=nside, NES_fraction=0./NES_scaledown,
                                    WFD_fraction=0.31, SCP_fraction=0.15/SCP_scaledown,
                                    GP_fraction=0.15,
                                    wfd_dec_min=-62.5, wfd_dec_max=3.6)
    result['g'] = generate_goal_map(nside=nside, NES_fraction=0.2/NES_scaledown,
                                    WFD_fraction=0.44, SCP_fraction=0.15/SCP_scaledown,
                                    GP_fraction=0.15,
                                    wfd_dec_min=-62.5, wfd_dec_max=3.6)
    result['r'] = generate_goal_map(nside=nside, NES_fraction=0.46/NES_scaledown,
                                    WFD_fraction=1.0, SCP_fraction=0.15/SCP_scaledown,
                                    GP_fraction=0.15,
                                    wfd_dec_min=-62.5, wfd_dec_max=3.6)
    result['i'] = generate_goal_map(nside=nside, NES_fraction=0.46/NES_scaledown,
                                    WFD_fraction=1.0, SCP_fraction=0.15/SCP_scaledown,
                                    GP_fraction=0.15,
                                    wfd_dec_min=-62.5, wfd_dec_max=3.6)
    result['z'] = generate_goal_map(nside=nside, NES_fraction=0.4/NES_scaledown,
                                    WFD_fraction=0.9, SCP_fraction=0.15/SCP_scaledown,
                                    GP_fraction=0.15,
                                    wfd_dec_min=-62.5, wfd_dec_max=3.6)
    result['y'] = generate_goal_map(nside=nside, NES_fraction=0./NES_scaledown,
                                    WFD_fraction=0.9, SCP_fraction=0.15/SCP_scaledown,
                                    GP_fraction=0.15,
                                    wfd_dec_min=-62.5, wfd_dec_max=3.6)
    return result


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


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)
    parser.add_argument("--survey_length", type=float, default=365.25*10)
    parser.add_argument("--outDir", type=str, default="")
    parser.add_argument("--maxDither", type=float, default=0.7, help="Dither size for DDFs (deg)")
    parser.add_argument("--moon_illum_limit", type=float, default=40., help="illumination limit to remove u-band")
    parser.add_argument("--nexp", type=int, default=2)
    parser.add_argument("--scale_down", dest='scale_down', action='store_true')
    parser.set_defaults(scale_down=False)

    args = parser.parse_args()
    survey_length = args.survey_length  # Days
    outDir = args.outDir
    verbose = args.verbose
    max_dither = args.maxDither
    illum_limit = args.moon_illum_limit
    nexp = args.nexp
    scale_down = args.scale_down

    nside = 32
    per_night = True  # Dither DDF per night

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

    fileroot = 'carina_' 
    file_end = 'v1.7_'

    if scale_down:
        footprints_hp = nes_light_footprints(nside=nside)
        fileroot = fileroot +'scaleddown_'
    else:
        footprints_hp = standard_goals(nside=nside)

    observatory = Model_observatory(nside=nside)
    conditions = observatory.return_conditions()
    footprints = Footprint(conditions.mjd_start, sun_RA_start=conditions.sun_RA_start, nside=nside)
    for i, key in enumerate(footprints_hp):
        footprints.footprints[i, :] = footprints_hp[key]

    # Set up the DDF surveys to dither
    dither_detailer = detailers.Dither_detailer(per_night=per_night, max_dither=max_dither)
    details = [detailers.Camera_rot_detailer(min_rot=-camera_ddf_rot_limit, max_rot=camera_ddf_rot_limit), dither_detailer]
    euclid_detailers = [detailers.Camera_rot_detailer(min_rot=-camera_ddf_rot_limit, max_rot=camera_ddf_rot_limit),
                        detailers.Euclid_dither_detailer()]
    ddfs = generate_dd_surveys(nside=nside, nexp=nexp, detailers=details, euclid_detailers=euclid_detailers)

    greedy = gen_greedy_surveys(nside, nexp=nexp, footprints=footprints)
    blobs = generate_blobs(nside, nexp=nexp, footprints=footprints)

    sequence_dict = gen_carina_sequence()
    times_array = gen_carina_times()
    ha_dict = {'carina': [[17., 24.], [0., 7.]]}
    carina_survey = [Scheduled_ddfs(times_array, sequence_dict, ha_dict, detailers=details)]

    surveys = [carina_survey, ddfs, blobs, greedy]
    #surveys = [ddfs, blobs, greedy]
    run_sched(surveys, survey_length=survey_length, verbose=verbose,
              fileroot=os.path.join(outDir, fileroot+file_end), extra_info=extra_info,
              nside=nside, illum_limit=illum_limit)
