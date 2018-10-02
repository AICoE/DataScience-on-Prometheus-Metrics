#!/usr/bin/env bash

# mkdir data/prometheus.example.com/

time python format_to_pandas.py \
       	--metric go_goroutines \
	    --input data/prometheus.example.com \
	    --output data/prometheus.example.com_pkl \
	    --batch_size 20
