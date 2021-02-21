import glob

if __name__ == '__main__':

    files = glob.glob('*10yrs.db')
    files.sort()
    with open('rolling_maf.script', 'w') as f:

        for filename in files:
            print('python ../../scimaf_dir.py --db %s' % filename, file=f)

        for filename in files:
            print('python ../../glance_dir.py --db %s' % filename, file=f)
