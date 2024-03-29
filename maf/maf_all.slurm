#!/bin/bash

## Job Name

#SBATCH --job-name=maf

## Allocation Definition

## On mox and ikt, the account and partition options should be the same.
#SBATCH --account=astro
#SBATCH --partition=astro

## Resources

## Nodes

#SBATCH --nodes=1   

## Walltime (hours:min:sec) Do not specify a walltime substantially more than your job needs.

#SBATCH --time=24:00:00

## Memory per node. It is important to specify the memory since the default memory is very small.

## For mox, --mem may be more than 100G depending on the memory of your nodes.

## For ikt, --mem may be 58G or more depending on the memory of your nodes.

## See above section on "Specifying memory" for choices for --mem.

#SBATCH --mem=500G

## Specify the working directory for this job

#SBATCH --chdir=/gscratch/scrubbed/yoachim/sims_featureScheduler_runs1.7/maf

##turn on e-mail notification

#SBATCH --mail-type=ALL

#SBATCH --mail-user=yoachim@uw.edu

## export all your environment variables to the batch job session

#SBATCH --export=all

## Set up the evironment
source /gscratch/astro/yoachim/lsst/loadLSST.bash
setup sims_maps -t $USER
setup sims_featureScheduler -t $USER -t sims_w_2020_02
setup sims_maf -t $USER -t sims_w_2020_02
setup sims_maf_contrib -t $USER -t sims_w_2020_02


cd /gscratch/scrubbed/yoachim/sims_featureScheduler_runs1.7/maf

## run all the baseline commands in parallel
module load parallel-20170722
## only need to do 5 at a time, since there are only that many in the list
cat sci_glance.sh | parallel -j 20

