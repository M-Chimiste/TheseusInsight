#!/usr/bin/env zsh
source "/Users/c/mambaforge/etc/profile.d/conda.sh"
conda activate paperpal
python run_paperpal.py --receiver-address "mark.salacinski@gmail.com, christian.j.merrill@gmail.com"
conda deactivate