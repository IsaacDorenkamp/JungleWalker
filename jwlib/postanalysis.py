import wx

# Meant for doing statistical analysis
# with the data from analysis.
class PostAnalysisPanel(wx.Panel):
    def __init__(self, parent, reglist, datapoints, model):
        wx.Panel.__init__(self, parent)
        self.__regs = reglist
        self.__dpts = datapoints
        self.__model = model

        # Where do we go from here? How did it disappear? It's hard to see with our own eyes
        # These times (these lies), we've been hypnotized - Pillar

        
