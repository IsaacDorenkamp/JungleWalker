# Analysis System

import math
import modellib
import random
import threading
import time

import multiprocessing as mp

import wx
import wx.lib.newevent

# traceback - debug only!
import traceback

StatusChangedEvent, EVT_STATUS_CHANGED = wx.lib.newevent.NewEvent()

# Analysis module uses the FastSimulation, an alternative to simulation
# which directly takes in a dictionary associating protein names to tuples
# containing truth tables and a list of regulators

def gen_rand_from_range(ers, precision=1):
    return ((math.floor( (random.random() * (ers[1] - ers[0]) + ers[0]) * (10 ** precision)) / (10**precision)))

def runsim(argt):
    try:
        er = argt[0]
        i = argt[1]
        dc0 = argt[2]
        dc1 = argt[3]
        env = argt[4]
        envk = argt[5]
        points = argt[6]
        q = argt[7]
        ervk = argt[8]
        ext_env = {}
        for j in er.keys():
            ers = er[j]
            # ext_env[j] = ers[0] + (ers[1] - ers[0])*(float(i) / (points-1)) # old way
            ext_env[j] = gen_rand_from_range(ers) # new way # TODO: put inputs into output object so that input information can be tracked
        s = modellib.FastSimulation(ext_env, ervk, env, envk)
        avgs = {}
        for j in xrange(1, dc1+1):
            s.RunStep()
            state = s.GetState()
            if j == dc0:
                for k in envk:
                    avgs[k] = float(state[k])
            elif j > dc0:
                for k in envk:
                    diff = j - dc0
                    avgs[k] = (diff*avgs[k] + float(state[k])) / (diff+1)
        for i in avgs.keys():
            avgs[i] = avgs[i]*100 # convert to percentage
        q.put((avgs, ext_env))
    except Exception as e:
        q.put(Exception(traceback.format_exc()))

class AnalysisThread(threading.Thread):
    def __init__(self, ext_ranges, extrkeys, envdata, data_points, dc_start, dc_end, sb):
        threading.Thread.__init__(self)
        self.__external_ranges = ext_ranges
        self.__env = envdata
        self.__envk = envdata.keys()
        self.__ervk = extrkeys
        self.__points = data_points
        self.__dc_range = (dc_start, dc_end)
        self.__statusbar = sb
        self.__data_points = []

        self.__envk = self.__env.keys()

        self.p = None
        
    def run(self):
        sce = StatusChangedEvent(percent=0.0, complete=False)
        wx.PostEvent(self.__statusbar, sce)
        self.p = mp.Pool(processes=16)
        argts = []
        q = mp.Manager().Queue()
        for i in xrange(0, self.__points):
            argts.append((self.__external_ranges, i, self.__dc_range[0], self.__dc_range[1], self.__env, self.__envk, self.__points, q, self.__ervk))

        t = float(time.time()*1000)
        self.p.map_async(runsim, argts)

        data = []
        for i in xrange(0, self.__points):
            g = q.get()
            if isinstance(g, Exception):
                raise g
            data.append(g)
            sce = StatusChangedEvent(percent = float(i+1) / self.__points, complete=False)
            wx.PostEvent(self.__statusbar, sce)
        #data.sort(key=lambda s:s[1]) # OLD CODE
        #ndata = []
        #for i in data:
        #    ndata.append(i[0])
        output_data = {}
        input_data = {}
        for i in data:
            odata = i[0]
            for j in odata.keys():
                if j in output_data.keys():
                    output_data[j].append(odata[j])
                else:
                    output_data[j] = [odata[j]]
            idata = i[1]
            for j in idata.keys():
                if j in input_data.keys():
                    input_data[j].append(idata[j])
                else:
                    input_data[j] = [idata[j]]
                    
        self.__data_points = (output_data, input_data)
        total = float(time.time()*1000) - t
        sce = StatusChangedEvent(percent = 1.0, complete=True, time=total)
        wx.PostEvent(self.__statusbar, sce)
            
    def GetRegulators(self):
        return self.__env.keys()
    def GetDataPoints(self):
        return self.__data_points

    def Stop(self):
        if self.p != None:
            self.p.close()
            self.p.terminate()
            self.p.join()
