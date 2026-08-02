from complete_pipeline import frequency_sweep

results = frequency_sweep(
    start_freq  = 100,
    end_freq    = 110,
    step        = 5,
    n_averages  = 1,
    exposure_us = 40000,
    gain        = 0.0,
    output_dir  = "/Users/patrickmulikuza/Desktop/sweep_output4",
)
