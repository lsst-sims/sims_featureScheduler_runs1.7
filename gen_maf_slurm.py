import glob


if __name__ == "__main__":

    dbfiles = glob.glob('*10yrs.db')
    with open('maf_dir.script', 'w') as f:
        for filename in dbfiles:
            print('python ../../glance_dir.py --db %s' % filename, file=f)

    