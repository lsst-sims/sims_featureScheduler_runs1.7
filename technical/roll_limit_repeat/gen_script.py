
weights = [0.75, 0.9]
slices = [2, 3]
nrws = [-6., -3., -1., 0.]

command = 'python rolling_nm.py '
with open('run_rolling.script', 'w') as f:
    for weight in weights:
        for slice_val in slices:
            for nrw in nrws:
                result = command + '--nslice %i --fpw %f --nrw %f' % (slice_val, weight, nrw)

                print(result, file=f)
