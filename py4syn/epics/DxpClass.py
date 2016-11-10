"""Dxp Class

Python Class for EPICS Dxp Control.

:platform: Unix
:synopsis: Python Class for EPICS Spectro control.

.. moduleauthor:: Gabriel Fedel <gabriel.fedel@lnls.br>
.. based on dxpclass from Juliano Murari and Pilatus Class from Henrique Almeida
    .. note:: /10/2016 [gabrielfedel]  first version released
"""
from epics import PV, ca
from py4syn.epics.StandardDevice import StandardDevice
from py4syn.epics.ICountable import ICountable
import numpy as np
from threading import Eventa
from py4syn.utils.timer import Timer


class Dxp(StandardDevice, ICountable):


    # CONSTRUCTOR OF DXP CLASS
    def __init__(self, mnemonic, numberOfChannels=4, numberOfRois=32, pv, dxpType="mca", responseTimeout = 15 ):
        """ Constructor
        responseTimeout : how much time to wait dxp answer
        """
        super().__init__(mnemonic)
        self.acquireChanged = Event()
        self.acquiring = False

        # TODO: removes after teste
        # determines the exposition time (live time)
        #self.pvDxpTime = PV(pv+":PresetLive.VAL")
        # determines the start of counting
        self.pvDxpEraseStart = PV(pv+":EraseStart.VAL")
        # determines mode of counting (Live Time, Real Time, ...)
        self.pvDxpPresetMode = PV(pv+":PresetMode.VAL")

        self.pvDxpStop = PV(pv+":StopAll.VAL")
        # store all channels
        self.pvDxpChannels = []
        # store ROIs
        self.pvDxpRois = []

        # store Acquire Time for each channel
        self.pvDxpAcquireTime = []


        for c in range(0, numberOfChannels):
            # store each channel
            self.pvDxpChannels.append(PV(pv+":"+dxpType+str(c+1)))
            # for each channel store the PV for AcquireTime
            self.pvDxpAcquireTime.append(PV(pv+":" + dxpType + "%d.PLTM" % (c+1)))
            self.pvDxpRois.append([])
            # storeing each ROI in your channel
            for r in range(0,numberOfRois):
                self.pvDxpRois[c].append(PV(pv+":"+dxpType+str(c+1)+'.R'+str(r)))

        self.pvDxpAcquiring = PV(pv+":Acquiring", self.onValChange)
        self.pvDxpAcquire.add_callback(self.statusChange)
        self.channels = numberOfChannels
        self.dxpType = dxpType
        self.rois = numberOfRois

        self.responseTimeout = responseTimeout
        self.timer = Timer(self.responseTimeout)

    def statusChange(self, value, **kw):
        """
        Helper callback used to wait for the end of the acquisition.
        """
        self.acquiring = value
        # threads waiting are awakened
        self.acquireChanged.set()

    def setCountTime(self, time):
        """
        Method to set the count time of a scaler device.

        Parameters
        ----------
        time : `float`
            Count time to set to scaler device .

        Returns
        -------
        out : None
        """
        for i in range(0,self.numberOfChannels):
            self.pvAcquireTime[i].put(time, wait=True)
        self.timer = Timer(time + self.responseTime)

    def getCountTime(self):
        return self.pvDxpTime.get()

    def setCountStop(self):
        self.pvDxpStop.put(1, wait = True)

    def getValueChannel(self, channel, asnumpy = True, **kwargs):
        """Return intensity
        channel is on format mcaC.Rr, where C is  the channel and
        r is the ROI"""
        c = int(channel[3]) - 1 
        if(len(channel) > 4):
           r = int(channel[5])
           return self.pvDxpRois[c][r]
        else:
            # TODO on this way returns the points. Find a better way
            # That work for many points, probably remove asnumpy
            return self.pvDxpChannels[c].get(as_numpy = asnumpy)

# TODO: remove after confirm that is not necessary
#    def getIntensityInTime(self, time, channel=2):
#        self.setCountTime(time)
#        self.setCountStart()
#        self.wait()
#        return self.getIntensity(channel)

    def isCountRunning(self):
        return (self.pvDxpAcquiring.get())

    def wait(self):
        """
        Blocks until the acquisition completes.
        """
        if self.acquiring == False:
            return

        self.acquireChanged.clear()
        # while acquiring and not time out waits
        # TODO: find a better way to do this
        while self.acquiring and self.timer.check():
            self.acquireChanged.wait(0.001)
            self.acquireChanged.clear()

        if self.timer.expired():
            raise RuntimeError('DXP is not answering')


    def canMonitor(self):
        """ Returns false indcating Dxp cannot be use as a counter monitor"""
        return False

    def canStopCount(self):
         """
        Returns true indicating that Dxp has a stop command.
        """
        return True

    def getValue(self, **kwargs):
        """
        This is a dummy method that always returns zero, which is part of the
        :class:`py4syn.epics.ICountable` interface. Dxp does not return
        a value while scanning. Instead, it stores a mca file with result .
        """
        if(kwargs):
            return self.getValueChannel(kwargs['channel'], kwargs['asnumpy'])
        return self.getValueChannel()

    def isCounting(self):
        return self.acquiring

    def startCount(self):
        """ Starts acquiring an spectrum
        It's necessary to call setCounTime before"""

        if self.acquiring:
            raise RuntimeError('Already counting')

        self.acquiring = True
        self.pvEraseStart.put(1)
        # resets initial time value
        self.timer.mark()

    def stopCount(self):
        self.setCountStop()

    def setPresetValue(self, channel, val):
        """Dummy method"""
        pass

    def close(self):
        """Stops an ongoing acquisition, if any, and puts the EPICS IOC in idle state."""
        self.pvDxpStop.put(1, wait=True)
