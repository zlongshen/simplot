import hashlib
import os
import numpy
import cPickle as pickle

###############################################################################

def unique_str_from_files(*filelist):
    #join list of file names
    uniquestr = "_".join(filelist)
    #now get last modified time
    uniquestr += "_".join(( str(os.path.getmtime(f)) for f in filelist ))
    #now add the last 
    
    #hash the resulting string
    uniquestr = hashlib.md5(uniquestr).hexdigest()
    return uniquestr

###############################################################################

def cache(uniquestr, callable_):
    '''A simple interface for CacheNumpy object.
    If a cache already exists it reads it,
    otherwise is evaluates the callable_ (with no arguments)
    and expects it to return data is a form that can be written to disk. 
    '''
    cn = CachePickle(uniquestr)
    if cn.exists():
        data = cn.read()
    else:
        data = callable_()
        cn.write(data)
    return data    

def cache_numpy(uniquestr, callable_):
    '''As cache but for numpy arrays. 
    '''
    cn = CacheNumpy(uniquestr)
    if cn.exists():
        data = cn.read()
    else:
        data = callable_()
        cn.write(data)
    return data

###############################################################################

class Cache(object):
    def __init__(self, uniquestr, prefix="tmp", tmpdir="/tmp/simplot_cache"):
        self._uniquestr = uniquestr
        self._tmpdir = tmpdir
        self._prefix = prefix
        
    def tmpfilename(self):
        uniquestr = self._uniquestr
        hashstr = hashlib.md5(uniquestr).hexdigest()
        tmpdir = self._tmpdir
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        return "".join([tmpdir,
                        os.sep,
                        "_".join((self._prefix, hashstr)),
                        ".bin",
                        ])
    
    def exists(self):
        return os.path.exists(self.tmpfilename()) 

###############################################################################

class CacheNumpy(Cache):
    def __init__(self, uniquestr, prefix="tmp", tmpdir="/tmp/simplot_cache"):
        super(CacheNumpy, self).__init__(uniquestr, prefix, tmpdir)
    
    def read(self):
        fname = self.tmpfilename()
        infile = file(fname, "rb")
        return numpy.load(infile)
    
    def write(self, data):
        fname = self.tmpfilename()
        outfile = file(fname, "wb")
        numpy.save(outfile, data)
        return

###############################################################################

class CachePickle(Cache):
    def __init__(self, uniquestr, prefix="tmp", tmpdir="/tmp/simplot_cache"):
        super(CachePickle, self).__init__(uniquestr, prefix, tmpdir)
    
    def read(self):
        fname = self.tmpfilename()
        with open(fname, "rb") as infile:
            data = pickle.load(infile)
        return data
    
    def write(self, data):
        fname = self.tmpfilename()
        with open(fname, "wb") as outfile:
            pickle.dump(data, outfile)
        return

###############################################################################

def _test_numpy_cache():
    test_dict = { "A":1, "B":2, "C":3 }
    test_numpy = numpy.ones(shape=(3, 2))
    def func_dict():
        return test_dict
    def func_numpy():
        return test_numpy
    assert cache("_test_simplot_cache_1", func_dict) == test_dict
    assert numpy.array_equal( cache_numpy("_test_simplot_cache_2", func_numpy), test_numpy)
    print "_test_numpy_cache success!"
    return

###############################################################################

def main():
    _test_numpy_cache()
    _test_numpy_cache()
    return

if __name__ == "__main__":
    main()
