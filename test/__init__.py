import sys
from os.path import abspath, join

if __name__ == '__main__':
    src_dir = abspath(join(__file__, '..', '..'))
    sys.path.append(src_dir)
    this_module = sys.modules[__name__]
    for name in dir(this_module):
        if name.startswith('test'):
            getattr(this_module, name)()
    print('All tests completed successfully')
