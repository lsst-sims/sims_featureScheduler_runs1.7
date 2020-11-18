# sims_featureScheduler_runs1.7
Even more simulated Rubin Observatory surveys


# Not Yet Released

# Notes

* Default to 2x15s visits rather than 1x30s as in previous releases. This results in a significant decrease in the total number of visits compared to earlier releases.
* Updated the telescope kinematic model. Previous releases had bugs that let observations be taken below the altitude limit, as well as unphysical combinations of telescope rotator angles.
* Improved rolling candence with scalable rolling strength



# Run Directories

## baseline17

Our latest baseline run. 

## rolling

The latest rolling cadence simulations with the classic footprint

## rolling_nm

Same as rolling, only without modulating nightly North/South emphasis.

## euclid_dither

Use a unique dither pattern for the Euclid DDF pointing to better match the fooprint of the Euclid field.

## pair_times

Vary the amount of time we try to take visit pairs on.

## twi_pairs

Takes twilight observations as pairs. Run with and without trying to re-observe areas in twilight that have already been observed in the night.

## u_long

Take u-band observations as single snaps, and test increasing u-band exposure times. Note, DDF u-band still needs to be updated.

## wfd_cadence_drive

An experiment where long gaps in g-band exposures are avoided, even if that means observing g in bright time.
