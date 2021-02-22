
scales = [0.75, 0.9]
slices = [2, 3]
nrws = [-6., -3., -1., 0.]
weights = [0.6, 0.9, 1.2]

command = 'python rolling_nm.py '
with open('run_rolling.script', 'w') as f:
    for scale in scales:
        for weight in weights:
            for slice_val in slices:
                for nrw in nrws:
                    result = command + '--nslice %i --fpw %.1f --nrw %.1f --scale %.2f' % (slice_val, weight, nrw, scale)

                    print(result, file=f)
