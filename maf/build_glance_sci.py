import glob


if __name__ == '__main__':

    files = glob.glob('*.db')
    with open('sci_glance.sh', 'w') as f:
        for filename in files:
            print('python ../scimaf_dir.py --db %s' % filename, file=f)
            print('python ../glance_dir.py --db %s' % filename, file=f)
