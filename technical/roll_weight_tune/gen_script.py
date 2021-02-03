
weights = [0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3.0]
slices = [2, 3]
contig = [True, False]

command = 'python rolling_nm.py '
with open('run_rolling.script', 'w') as f:
    for weight in weights:
        for slice_val in slices:
            for cont in contig:
                result = command + '--nslice %i --fpw %f' % (slice_val, weight)
                if cont:
                    result += ' --uncontiguous'
                print(result, file=f)
