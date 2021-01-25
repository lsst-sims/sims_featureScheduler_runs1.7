# sims_featureScheduler_runs1.7

Even more simulated Rubin Observatory surveys

Runs available at:  https://lsst.ncsa.illinois.edu/sim-data/sims_featureScheduler_runs1.7/

# Notes

* Default to 2x15s visits rather than 1x30s as in previous releases. This results in a significant decrease in the total number of visits compared to earlier releases.
* Updated the telescope kinematic model. Previous releases had bugs that let observations be taken below the altitude limit, as well as unphysical combinations of telescope rotator angles.
* Improved rolling candence simulations with scalable rolling strength



# Run Directories

## baseline17

baseline_nexp1_v1.7_10yrs.db  
baseline_nexp2_v1.7_10yrs.db  

Our latest baseline runs, with 1x30s and 2x15s visits. Note all the otehr runs in this release are done with 2x15s snaps, so baseline_nexp2_v1.7_10yrs.db is the best run to use for comparisons. 

## rolling

rolling_scale0.2_nslice2_v1.7_10yrs.db  
rolling_scale0.2_nslice3_v1.7_10yrs.db  
rolling_scale0.4_nslice2_v1.7_10yrs.db  
rolling_scale0.4_nslice3_v1.7_10yrs.db  
rolling_scale0.6_nslice2_v1.7_10yrs.db  
rolling_scale0.6_nslice3_v1.7_10yrs.db  
rolling_scale0.8_nslice2_v1.7_10yrs.db  
rolling_scale0.8_nslice3_v1.7_10yrs.db  
rolling_scale0.9_nslice2_v1.7_10yrs.db  
rolling_scale0.9_nslice3_v1.7_10yrs.db  
rolling_scale1.0_nslice2_v1.7_10yrs.db  
rolling_scale1.0_nslice3_v1.7_10yrs.db  

The latest rolling cadence simulations with the classic footprint. The strength of the rolling is varried between 20 and 100%. We also try dividing the wide-fast-deep area in half (nslice2) and thirds (nsilce3). The nslice3 runs do not increase the cadence as much as might be expected, they probably need some basis function weight adjustments. 



## rolling_nm

rolling_nm_scale0.2_nslice2_v1.7_10yrs.db  
rolling_nm_scale0.2_nslice3_v1.7_10yrs.db  
rolling_nm_scale0.4_nslice2_v1.7_10yrs.db  
rolling_nm_scale0.4_nslice3_v1.7_10yrs.db  
rolling_nm_scale0.6_nslice2_v1.7_10yrs.db  
rolling_nm_scale0.6_nslice3_v1.7_10yrs.db  
rolling_nm_scale0.8_nslice2_v1.7_10yrs.db  
rolling_nm_scale0.8_nslice3_v1.7_10yrs.db  
rolling_nm_scale0.9_nslice2_v1.7_10yrs.db  
rolling_nm_scale0.9_nslice3_v1.7_10yrs.db  
rolling_nm_scale1.0_nslice2_v1.7_10yrs.db  
rolling_nm_scale1.0_nslice3_v1.7_10yrs.db  

Same as rolling, only without modulating nightly North/South emphasis.

## ddf_dither

ddf_dither0.00_v1.7_10yrs.db  
ddf_dither0.05_v1.7_10yrs.db  
ddf_dither0.10_v1.7_10yrs.db  
ddf_dither0.30_v1.7_10yrs.db  
ddf_dither0.70_v1.7_10yrs.db  
ddf_dither1.00_v1.7_10yrs.db  
ddf_dither1.50_v1.7_10yrs.db  
ddf_dither2.00_v1.7_10yrs.db  

Varying the size of the deep drilling field dither size between 0 and 2 degrees.


## euclid_dither

euclid_dither1_v1.7_10yrs.db  
euclid_dither2_v1.7_10yrs.db  
euclid_dither3_v1.7_10yrs.db  
euclid_dither4_v1.7_10yrs.db  
euclid_dither5_v1.7_10yrs.db  

Use a unique dither pattern for the Euclid DDF pointing to better match the fooprint of the Euclid field. 

## pair_times

pair_times_11_v1.7_10yrs.db  
pair_times_22_v1.7_10yrs.db  
pair_times_33_v1.7_10yrs.db  
pair_times_44_v1.7_10yrs.db  
pair_times_55_v1.7_10yrs.db  

Vary the amount of time we try to take visit pairs on. The baseline attempts to observe pairs seperated by 22 minutes. Here we vary between 11 and 55 minute pairs.

## twi_pairs

twi_pairs_mixed_repeat_v1.7_10yrs.db  
twi_pairs_mixed_v1.7_10yrs.db  
twi_pairs_repeat_v1.7_10yrs.db  
twi_pairs_v1.7_10yrs.db  

Takes twilight observations as pairs. Run with and without trying to re-observe areas in twilight that have already been observed in the night. Also taking pairs in twilight in the same filter or in different filters.

## twi_neo

twi_neo_pattern1_v1.7_10yrs.db  
twi_neo_pattern2_v1.7_10yrs.db  
twi_neo_pattern3_v1.7_10yrs.db  
twi_neo_pattern4_v1.7_10yrs.db  
twi_neo_pattern5_v1.7_10yrs.db  
twi_neo_pattern6_v1.7_10yrs.db  
twi_neo_pattern7_v1.7_10yrs.db  

An updated attempt at using twilight time for a NEO survey. These simulations include a large number of 1s observations. We still need to verify that the camera and network could handle taking so many short exposures.

## u_long

u_long_ms_30_v1.7_10yrs.db  
u_long_ms_40_v1.7_10yrs.db  
u_long_ms_50_v1.7_10yrs.db  
u_long_ms_60_v1.7_10yrs.db  

Take u-band observations as single snaps, and test increasing u-band exposure times. Note, DDF u-band observations are still the default. 

## wfd_cadence_drive

cadence_drive_gl100_gcbv1.7_10yrs.db  
cadence_drive_gl100v1.7_10yrs.db  
cadence_drive_gl200_gcbv1.7_10yrs.db  
cadence_drive_gl200v1.7_10yrs.db  
cadence_drive_gl30_gcbv1.7_10yrs.db  
cadence_drive_gl30v1.7_10yrs.db  

An experiment where long gaps in g-band exposures are avoided, even if that means observing g in bright time. We test different limits on how many g-observations are taken and if the blob scheduler tries to mantain contiguous areas.

