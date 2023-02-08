#!/bin/tcsh
#SBATCH --job-name=st_access
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=12:00:00
#SBATCH --mem-per-cpu=16GB
#SBATCH --mail-type=FAIL
#SBATCH --mail-type=END
#SBATCH --mail-user=jparkgeo@illinois.edu

module purge
cd /data/cigi/common/jparkgeo/ST_ICU_Access
source /data/keeling/a/jparkgeo/.bashrc

conda run -n access python other_notebooks/Accessibility_Measurements.py