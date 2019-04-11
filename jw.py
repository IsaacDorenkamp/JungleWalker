# Jungle Walker
# A software to load CellCollective models
# for purposes of running simulations and
# performing analysis, as well as exploring
# the logic of individual nodes.

import copy
import glob
import config

import time

import wx
import wx.adv
import wx.grid as wxgrid
import wx.lib.inspection

import requests.exceptions

import threading

import pprint

import math
import sys

app = wx.App()

# Some modules depend on the creation of the wx app (i.e. for fonts)
import jwlib as lib

#Global Stuff
global BIG_FONT
global MEDIUM_FONT
global SMALL_FONT
global RBOX_PADDING
global WORDWRAP_TOLERANCE

BIG_FONT = wx.Font(18, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
MEDIUM_FONT = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
RBOX_PADDING = 20
WORDWRAP_TOLERANCE = 5

# My own word wrap calculator, because whoever wrote
# wx's is an idiot
def BreakWordWrap(word, width, dc):
    if word == '':
        return ''
    pieces = word.split(' ')
    if dc.GetTextExtent(pieces[0])[0] > width - WORDWRAP_TOLERANCE:
        return '\n' + word
    out = ""
    for i in pieces:
        lines = out.split('\n')
        last_line = lines[len(lines)-1]
        if dc.GetTextExtent(last_line + i)[0] > width - WORDWRAP_TOLERANCE:
            out += "\n" + i + " "
        else:
            out += i + " "
    return out

class JungleWalker(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Jungle Walker %s" % config.VERSION, size=(500, 500))
        self.Centre()
        self.Maximize(True)

        self.locale = wx.Locale(wx.LANGUAGE_ENGLISH) # Prevents breakage by some controls

        self.SetMinSize((750, 625))
        
        self.extenv = []
        self.env = {}

        self.__mutation_set = {}

        self.__layout_callbacks = []

        self.prot = None
        self.ext_prot = None

        self.RunningAnalysis = False
        self.RunningSim = False
        self.AnalysisThread = None
        self.Simulator = None

        self.__resized = True # initially perform resize op

        self.__session = lib.CCApi.CCSession()

        self.__model = None

        # UI-to-node maps
        self.__intlist_to_node = []
        self.__extlist_to_node = []

        self.__extdets_to_node = []

        self.__config_ui()

        self.__ui_init = False

    def SetSimulator(self, sim):
        self.Simulator = sim

    def GetSimulator(self):
        return self.Simulator

    def __before_close(self, evt=None):
        if self.Simulator != None:
            self.Simulator.Stop()
        if self.AnalysisThread != None:
            self.AnalysisThread.Stop()
        self.Destroy()
        sys.exit(0)
    
    def __relayout(self, evt=None):
        self.lbox.SetMaxSize((math.floor(self.GetSize()[0] / 4), self.GetSize()[1]))

        if self.__ui_init:
            if self.SimulationPanel.GetSize()[0] == 0:
                exs = self.ExternalActivity.GetTargetWindow().GetVirtualSize()[0] + 30
            else:
                exs = min(self.ExternalActivity.GetTargetWindow().GetVirtualSize()[0] + 30, self.SimulationPanel.GetSize()[0] / 2)

            if self.AnalysisPanel.GetSize()[0] == 0:
                aexs = self.AnalysisExternalActivity.GetTargetWindow().GetVirtualSize()[0] + 20
            else:
                aexs = min(self.AnalysisExternalActivity.GetTargetWindow().GetVirtualSize()[0] + 20, self.AnalysisPanel.GetSize()[0] / 2)

            self.ExternalActivity.SetMinSize((exs, self.SimulationPanel.GetSize()[1]))
            self.AnalysisExternalActivity.SetMinSize((aexs, self.AnalysisPanel.GetSize()[1]))
        else:
            if not self.IsMaximized():
                self.__ui_init = True

        self.viewboxer.Layout()
        self.boxer.Layout()
        self.__rewrap_text()
        self.TruthTablePanel_Boxer.Layout()
        self.External_Boxer.Layout()

        for i in self.__layout_callbacks:
            if callable(i):
                i()

    def OnFinalizeResize(self, event):
        if self.__resized:
            self.__set_load_msg(self.loading_lbl.GetLabelText())
            wx.CallAfter(self.__relayout)
            wx.CallAfter(self.TruthTable.FixSizes)
            self.__resized = False
            event.Skip()
        
    def OnResize(self, event):
        self.__resized = True
        event.Skip()

    def __config_ui(self):
        # Icon!
        try:
            self.SetIcon(wx.Icon('./icon.jpeg'))
        except IOError:
            print("no icon file :(")

        # Font!

        SMALL_FONT = self.GetFont()
        
        # Configure Menus
        menubar    = wx.MenuBar()
        file_menu  = wx.Menu()
        close_proj = file_menu.Append(wx.ID_ANY, 'Close Project', 'Close the current Workspace')
        exit_item  = file_menu.Append(wx.ID_EXIT, 'Exit', 'Exit JungleWalker')

        cc_menu = wx.Menu()
        load_item  = cc_menu.Append(wx.ID_ANY, 'Load Model', 'Load a model from CellCollective.')
        self.login_item = cc_menu.Append(wx.ID_ANY, 'Log In', 'Log In to CellCollective')

        window_menu = wx.Menu()
        self.__window = {}
        self.__window['tt'] = window_menu.AppendCheckItem(wx.ID_ANY, 'Truth Table for Selected Protein',
                                     'Display the truth table which details how the selected protein\'s regulators affect it')
        self.__window['ct'] = window_menu.AppendCheckItem(wx.ID_ANY, 'Condition Tester for Selected Protein',
                                     'A window which allows you to learn how a protein is regulated by activating and deactivating its regulators')
        self.__window['ec'] = window_menu.AppendCheckItem(wx.ID_ANY, 'External Component Details',
                                     'A window which allows you to see which internal components are regulated by the selected external component')
        self.__window['cg'] = window_menu.AppendCheckItem(wx.ID_ANY, 'Component Graph', 'A window visibly displaying the node map.')
        self.__window['rs'] = window_menu.AppendCheckItem(wx.ID_ANY, 'Run Simulation',
                                     'Configure a simulation environment and begin a continuously running simulation of the model')
        self.__window['ap'] = window_menu.AppendCheckItem(wx.ID_ANY, 'Analysis', 'Configure a range of simulation environments and run a large number of simulations'
                                                          + ' very quickly to obtain data about how certain changes in environment affect certain nodes')
        self.__window['cp'] = window_menu.AppendCheckItem(wx.ID_ANY, 'Show Component Pane')

        self.__window['cp'].Check()

        menubar.Append(file_menu, '&File')
        menubar.Append(cc_menu, '&CellCollective')
        menubar.Append(window_menu, '&Windows')

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.__close_project, close_proj)
        self.Bind(wx.EVT_MENU, self.ShowModelDialog, load_item)
        self.Bind(wx.EVT_MENU, self.ShowAuthDialog, self.login_item)
        self.Bind(wx.EVT_MENU, self.OnExit, exit_item)
        
        self.Bind(wx.EVT_SIZE, self.OnResize)
        self.Bind(wx.EVT_IDLE, self.OnFinalizeResize)

        self.tb = wx.Panel(self, style=wx.SIMPLE_BORDER)
        self.bmp = {}
        self.bmp['login'] = wx.Bitmap('./img/login.bmp')
        self.bmp['logout'] = wx.Bitmap('./img/logout.bmp')
        lmask = wx.Mask(self.bmp['login'], wx.WHITE)
        self.bmp['login'].SetMask(lmask)
        lomask = wx.Mask(self.bmp['logout'], wx.WHITE)
        self.bmp['logout'].SetMask(lomask)
        mbmp = wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN)
        self.lmdl = wx.BitmapButton(self.tb, wx.ID_ANY, mbmp, size=(40, 40))
        self.lmdl.SetToolTip(wx.ToolTip("Load Model"))
        self.tb_model = wx.StaticText(self.tb, label="No Model Loaded.")
        self.tb_username = wx.StaticText(self.tb, label="Not Logged In.")
        self.lbtn = wx.BitmapButton(self.tb, wx.ID_ANY, self.bmp['login'], size=(40, 40))
        self.lbtn.SetToolTip(wx.ToolTip("Log In"))
        curs = wx.Cursor(wx.CURSOR_HAND)
        self.lmdl.SetCursor(curs)
        self.lbtn.SetCursor(curs)

        tbboxer = wx.BoxSizer()
        tbboxer.Add(self.lmdl, 0, wx.ALL, 5)
        tbboxer.Add(self.tb_model, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        tbboxer.AddStretchSpacer()
        tbboxer.Add(self.tb_username, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        tbboxer.Add(self.lbtn, 0, wx.ALL, 5)
        self.tb.SetSizer(tbboxer)

        self.tb.Bind(wx.EVT_BUTTON, self.ShowModelDialog, self.lmdl)
        self.tb.Bind(wx.EVT_BUTTON, self.ShowAuthDialog, self.lbtn)

        self.content = wx.Panel(self)

        # Configure Controls. First, two main panels.
        self.appview = wx.Panel(self.content)
        self.waitview = wx.Panel(self.content)# Set up wait view
        self.loading_lbl = wx.StaticText(self.waitview, wx.ID_ANY, "Loading Model...", style=wx.ALIGN_CENTER | wx.ST_NO_AUTORESIZE)
        self.loading_lbl.SetFont(BIG_FONT)
        waitviewsizer = wx.FlexGridSizer(3,1,0,0)
        p1 = wx.Panel(self.waitview)
        p2 = wx.Panel(self.waitview)
        waitviewsizer.Add(p1, 1, wx.EXPAND)
        waitviewsizer.Add(self.loading_lbl, 0, wx.ALIGN_CENTER | wx.EXPAND)
        waitviewsizer.Add(p2, 1, wx.EXPAND)
        waitviewsizer.AddGrowableRow(0)
        waitviewsizer.AddGrowableRow(1)
        waitviewsizer.AddGrowableRow(2)
        waitviewsizer.AddGrowableCol(0)
        self.waitview.SetSizer(waitviewsizer)

        self.waitview.Show(False)
        
        self.lbox = wx.Panel(self.appview)
        self.rbox = wx.Notebook(self.appview)

        self.cbox = wx.BoxSizer(wx.VERTICAL)

        self.cbox.Add(self.content, 1, wx.EXPAND)
        self.cbox.Add(self.tb, 0, wx.EXPAND)

        self.SetSizer(self.cbox)
        
        self.viewboxer = wx.BoxSizer()
        self.viewboxer.Add(self.appview, 1, wx.EXPAND)
        self.viewboxer.Add(self.waitview, 1, wx.EXPAND)
        self.content.SetSizer(self.viewboxer)

        self.rbox.SetBackgroundColour('#EEEEEE')
        self.rbox.SetFont(SMALL_FONT)

        self.boxer = wx.BoxSizer()

        self.boxer.Add(self.lbox, 0, wx.EXPAND)
        self.boxer.Add(self.rbox, 1, wx.EXPAND)
        
        self.appview.SetSizer(self.boxer)

        # Second, top and bottom panels on the left.
        tbox = wx.Panel(self.lbox)
        bbox = wx.Panel(self.lbox)

        self.lboxer = wx.BoxSizer(wx.VERTICAL)

        self.lboxer.Add(tbox, wx.ID_ANY, wx.EXPAND | wx.TOP, 0)
        self.lboxer.Add(bbox, wx.ID_ANY, wx.EXPAND | wx.BOTTOM, 0)

        self.lbox.SetSizer(self.lboxer)

        # Third, list boxes on the left.
        internal_label = wx.StaticText(tbox, wx.ID_ANY, "Internal Components")
        self.InternalList = wx.ListBox(tbox, style=wx.NO_BORDER | wx.HSCROLL)

        self.tboxer = wx.BoxSizer(wx.VERTICAL)

        self.tboxer.Add(internal_label, 0, wx.ALL, border=5)
        self.tboxer.Add(self.InternalList, 1, wx.EXPAND | wx.CENTER)

        tbox.SetSizer(self.tboxer)
        
        external_label = wx.StaticText(bbox, wx.ID_ANY, "External Components")
        self.ExternalList = wx.ListBox(bbox, style=wx.NO_BORDER | wx.HSCROLL)

        self.bboxer = wx.BoxSizer(wx.VERTICAL)

        self.bboxer.Add(external_label, 0, wx.ALL, border=7)
        self.bboxer.Add(self.ExternalList, 1, wx.EXPAND | wx.CENTER)

        bbox.SetSizer(self.bboxer)

        # Fourth, handle stuff in the right panel.
        self.TruthTablePanel = wx.Panel(self.rbox)
        
        self.ProteinName = wx.StaticText(self.TruthTablePanel, wx.ID_ANY, "No internal components loaded :(")
        self.ProteinName.SetFont(BIG_FONT)

        self.TruthTable = lib.TruthTable(self.TruthTablePanel)
        self.TruthTable.SetDefaultCellFont(SMALL_FONT)
        self.TruthTable.SetPadding(RBOX_PADDING)

        self.TruthTablePanel_Boxer = wx.BoxSizer(wx.VERTICAL)

        self.TruthTablePanel_Boxer.Add(self.ProteinName, 0, wx.RIGHT | wx.LEFT | wx.TOP, RBOX_PADDING)
        self.TruthTablePanel_Boxer.Add(self.TruthTable, 1, wx.CENTER | wx.EXPAND | wx.ALL, RBOX_PADDING)

        self.TruthTablePanel.SetSizer(self.TruthTablePanel_Boxer)

        # Fifth, configure tab panel for individual simulation
        self.MiniSimPanel = lib.LogicDiagram(self.rbox)
        self.MiniSimPanel.SetBackgroundColour('white')

        # Sixth, configure tab panel for details of external components
        self.ExternalDetails = wx.Panel(self.rbox)
        self.ExternalDetails.SetFont(MEDIUM_FONT)

        self.SelectedExt = wx.StaticText(self.ExternalDetails, label="Nothing loaded :(")
        self.SelectedExtReg = wx.ListBox(self.ExternalDetails)

        self.SelectedExt.SetFont(BIG_FONT)

        self.External_Boxer = wx.BoxSizer(wx.VERTICAL)

        self.External_Boxer.Add(self.SelectedExt, 0, wx.TOP, 5)
        self.External_Boxer.Add(self.SelectedExtReg, 0, wx.CENTER | wx.EXPAND)

        self.ExternalDetails.SetSizer(self.External_Boxer)

        # Seventh, configure tab panel for running simulations
        self.SimulationPanel = wx.Panel(self.rbox)

        self.ExternalActivity = lib.SliderList(self.SimulationPanel)

        self.StartSimulator = wx.Panel(self.SimulationPanel)

        self.SimulatorToolbar = wx.Panel(self.StartSimulator)
        self.SimulatorConfig = wx.ScrolledWindow(self.StartSimulator)
        self.SimulatorResults = wx.Panel(self.StartSimulator, style=wx.SIMPLE_BORDER)

        self.SimulatorToolbar.SetBackgroundColour('#dddddd')
        sv_ext = wx.BitmapButton(self.SimulatorToolbar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE), size=(48, 48))
        sv_ext.SetToolTip(wx.ToolTip('Save Environment Configuration'))
        ld_ext = wx.BitmapButton(self.SimulatorToolbar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN), size=(48, 48))
        ld_ext.SetToolTip(wx.ToolTip('Load Environment Configuration'))
        sm_res = wx.BitmapButton(self.SimulatorToolbar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_UNDO), size=(48, 48))
        sm_res.SetToolTip(wx.ToolTip('Reset Configuration'))

        c = wx.Cursor(wx.CURSOR_HAND)

        sv_ext.SetCursor(c)
        ld_ext.SetCursor(c)

        sv_ext.Bind(wx.EVT_BUTTON, self.__pref_sim_save)
        ld_ext.Bind(wx.EVT_BUTTON, self.__pref_sim_load)
        sm_res.Bind(wx.EVT_BUTTON, self.__sim_reset)

        toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        toolbar_sizer.Add(sv_ext, 0, wx.ALL, 10)
        toolbar_sizer.Add(ld_ext, 0, wx.ALL, 10)
        toolbar_sizer.Add(sm_res, 0, wx.ALL, 10)
        self.SimulatorToolbar.SetSizer(toolbar_sizer)

        self.SimulatorConfig.ShowScrollbars(wx.SHOW_SB_DEFAULT, wx.SHOW_SB_DEFAULT)
        self.SimulatorConfig.SetScrollRate(3, 12)

        self.SimulationBoxer = wx.BoxSizer(wx.HORIZONTAL)
        self.SimulatorBoxer = wx.BoxSizer(wx.VERTICAL)

        self.SimulationBoxer.Add(self.ExternalActivity, 0, wx.EXPAND)
        self.SimulationBoxer.Add(self.StartSimulator, 1, wx.EXPAND)

        self.SimulatorBoxer.Add(self.SimulatorToolbar, 0, wx.ALL | wx.EXPAND)
        self.SimulatorBoxer.Add(self.SimulatorConfig, 1, wx.CENTER | wx.EXPAND)
        self.SimulatorBoxer.Add(self.SimulatorResults, 0, wx.ALL | wx.EXPAND)
        
        self.SimulationPanel.SetSizer(self.SimulationBoxer)
        self.StartSimulator.SetSizer(self.SimulatorBoxer)

        speed_label = wx.StaticText(self.SimulatorConfig, label="Simulation Speed:", style=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.SimulationLength = wx.SpinCtrl(self.SimulatorConfig, wx.ID_ANY, value="50", min=50, max=250, style=wx.ALIGN_CENTER)
        steps_label = wx.StaticText(self.SimulatorConfig, label="ms/step")

        mut_label = wx.StaticText(self.SimulatorConfig, label="Mutations:", style=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        mut_button = wx.Button(self.SimulatorConfig, label="Configure")

        self.SimulationGoButton = wx.Button(self.SimulatorConfig, label="Run Simulation")

        dummy  = wx.StaticText(self.SimulatorConfig, label="")
        dummy2 = wx.StaticText(self.SimulatorConfig, label="")

        self.SimConfigGridder = wx.GridBagSizer(10, 10)

        self.SimConfigGridder.Add(speed_label, pos=(1, 1), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        self.SimConfigGridder.Add(self.SimulationLength, pos=(1,2), span=(1,2), flag=wx.ALL | wx.EXPAND, border=5)
        self.SimConfigGridder.Add(steps_label, pos=(1,4), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT, border=5)

        self.SimConfigGridder.Add(mut_label, pos=(2,1), flag=wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.SimConfigGridder.Add(mut_button, pos=(2,2), span=(1,2), flag=wx.ALL | wx.EXPAND, border=5)

        self.SimConfigGridder.Add(self.SimulationGoButton, pos=(3,2), flag=wx.ALL | wx.EXPAND, border=5)
        self.SimConfigGridder.Add(dummy, pos=(0,4))
        self.SimConfigGridder.Add(dummy2, pos=(4,0))

        self.SimConfigGridder.AddGrowableCol(0)
        self.SimConfigGridder.AddGrowableCol(4)

        self.SimConfigGridder.AddGrowableRow(0)
        self.SimConfigGridder.AddGrowableRow(4)

        self.SimulatorConfig.SetSizer(self.SimConfigGridder)

        self.SimulationStatus = wx.StaticText(self.SimulatorResults, label="No task running", style=wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)
        self.SimulationStatus.SetFont(MEDIUM_FONT)

        self.ResultsSizer = wx.BoxSizer()

        self.ResultsSizer.Add(self.SimulationStatus, wx.ID_ANY, wx.ALL | wx.EXPAND, border=10)

        self.SimulatorResults.SetSizer(self.ResultsSizer)

        # Configure Analysis Panel
        self.AnalysisPanel = wx.Panel(self.rbox)
        self.AnalysisExternalActivity = lib.RangeSliderList(self.AnalysisPanel)
        self.AnalysisConfig = wx.Panel(self.AnalysisPanel)
        self.AnalysisForm = wx.Panel(self.AnalysisConfig)
        self.AnalysisStatusBar = lib.StatusPanel(self.AnalysisConfig, style=wx.SIMPLE_BORDER)
        self.AnalysisStatus = lib.TransparentStatus(self.AnalysisStatusBar)
        self.AnalysisStatus.SetFont(MEDIUM_FONT)
        self.AnalysisStatus.SetText("No task running.")

        self.AnalysisToolbar = wx.Panel(self.AnalysisConfig)
        self.AnalysisToolbar.SetBackgroundColour('#dddddd')
        a_sv_ext = wx.BitmapButton(self.AnalysisToolbar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE), size=(48, 48))
        a_sv_ext.SetToolTip(wx.ToolTip('Save Environment Configuration'))
        a_ld_ext = wx.BitmapButton(self.AnalysisToolbar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN), size=(48, 48))
        a_ld_ext.SetToolTip(wx.ToolTip('Load Environment Configuration'))
        a_sm_res = wx.BitmapButton(self.AnalysisToolbar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_UNDO), size=(48, 48))
        a_sm_res.SetToolTip(wx.ToolTip('Reset Configuration'))

        a_sv_ext.Bind(wx.EVT_BUTTON, self.__pref_analysis_save)
        a_ld_ext.Bind(wx.EVT_BUTTON, self.__pref_analysis_load)
        a_sm_res.Bind(wx.EVT_BUTTON, self.__analysis_reset)

        # Analysis Toolbar Sizing
        atb = wx.BoxSizer()
        atb.Add(a_sv_ext, 0, wx.ALL, 10)
        atb.Add(a_ld_ext, 0, wx.ALL, 10)
        atb.Add(a_sm_res, 0, wx.ALL, 10)
        self.AnalysisToolbar.SetSizer(atb)

        # Analysis Status Bar Sizing
        asbb = wx.BoxSizer(wx.VERTICAL)
        asbb.Add(self.AnalysisStatus, 1, wx.ALL | wx.EXPAND)
        self.AnalysisStatusBar.SetSizer(asbb)

        aboxer = wx.BoxSizer(wx.HORIZONTAL)

        aboxer.Add(self.AnalysisExternalActivity, 0, wx.ALL | wx.EXPAND)
        aboxer.Add(self.AnalysisConfig, 1, wx.ALL | wx.EXPAND)

        data_points_lbl = wx.StaticText(self.AnalysisForm, label="Number of Data Points:")
        self.AnalysisDataPoints = wx.SpinCtrl(self.AnalysisForm, value="10", min=2, max=2147483647, style=wx.ALIGN_CENTER)
        begin_dc = wx.StaticText(self.AnalysisForm, label="Begin data collection at frame")
        self.AnalysisBeginDC = wx.SpinCtrl(self.AnalysisForm, value="100", min=1, max=2147483647, style=wx.ALIGN_CENTER)
        end_dc = wx.StaticText(self.AnalysisForm, label="End data collection at frame")
        self.AnalysisEndDC = wx.SpinCtrl(self.AnalysisForm, value="800", min=1, max=2147483647, style=wx.ALIGN_CENTER)

        subm_pan = wx.Panel(self.AnalysisForm)
        analysis_ok = wx.Button(subm_pan, label="Run Analysis")

        sps = wx.BoxSizer(wx.VERTICAL)
        sps.Add(analysis_ok, 0, wx.ALL | wx.ALIGN_CENTER)
        subm_pan.SetSizer(sps)

        self.AnalysisGridder = wx.GridBagSizer(10, 10)

        self.AnalysisGridder.Add( wx.Panel(self.AnalysisForm), pos=(0,0), flag=wx.EXPAND | wx.ALL, border=5 )
        self.AnalysisGridder.Add( wx.Panel(self.AnalysisForm), pos=(5,3), flag=wx.EXPAND | wx.ALL, border=5 )
        self.AnalysisGridder.Add( data_points_lbl, pos=(1,1), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT )
        self.AnalysisGridder.Add( self.AnalysisDataPoints, pos=(1,2), flag=wx.EXPAND | wx.ALL, border=5 )
        self.AnalysisGridder.Add( begin_dc, pos=(2,1), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT )
        self.AnalysisGridder.Add( self.AnalysisBeginDC, pos=(2, 2), flag=wx.EXPAND | wx.ALL, border=5 )
        self.AnalysisGridder.Add( end_dc, pos=(3,1), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT )
        self.AnalysisGridder.Add( self.AnalysisEndDC, pos=(3,2), flag=wx.EXPAND | wx.ALL, border=5 )
        self.AnalysisGridder.Add( subm_pan, pos=(4,1), span=(1,2), flag=wx.EXPAND | wx.ALL, border=5 )

        self.AnalysisGridder.AddGrowableCol(0)
        self.AnalysisGridder.AddGrowableCol(3)
        self.AnalysisGridder.AddGrowableRow(0)
        self.AnalysisGridder.AddGrowableRow(5)

        acfgs = wx.BoxSizer(wx.VERTICAL)
        acfgs.Add(self.AnalysisToolbar, 0, wx.EXPAND)
        acfgs.Add(self.AnalysisForm, 1, wx.EXPAND)
        acfgs.Add(self.AnalysisStatusBar, 0, wx.EXPAND)
        self.AnalysisConfig.SetSizer(acfgs)

        self.AnalysisForm.SetSizer(self.AnalysisGridder)
        self.AnalysisPanel.SetSizer(aboxer)

        # Set up component graph
        self.GraphPanel = wx.Panel(self.rbox)

        self.CompGraph = lib.ComponentGraph(self.GraphPanel)

        gph_size = wx.BoxSizer(wx.VERTICAL)
        gph_size.Add( self.CompGraph, 1, wx.EXPAND )
        self.GraphPanel.SetSizer(gph_size)

        # Penultimately, configure tabs.
        # We start out with only one tab open, and if we do not add and
        # the remove the pages, then the panels will display *over* the
        # tab bar as little gray squares :(
        
        self.rbox.AddPage(self.SimulationPanel, '')
        self.rbox.AddPage(self.AnalysisPanel, '')
        self.rbox.AddPage(self.TruthTablePanel, '')
        self.rbox.AddPage(self.MiniSimPanel, '')
        self.rbox.AddPage(self.ExternalDetails, '')
        self.rbox.AddPage(self.GraphPanel, '')
        self.rbox.RemovePage(0)
        self.rbox.RemovePage(0)
        self.rbox.RemovePage(0)
        self.rbox.RemovePage(0)
        self.rbox.RemovePage(0)
        self.rbox.RemovePage(0)

        # When nothing's been loaded
        self.__set_load_msg("Select a model to load.")
        self.appview.Show(False)
        self.waitview.Show()

        # Finally, configure events.
        self.Bind(wx.EVT_BUTTON, self.__run_analysis, analysis_ok)
        self.Bind(wx.EVT_BUTTON, self.__run_sim, self.SimulationGoButton)
        self.Bind(wx.EVT_BUTTON, self.__config_mutations, mut_button)
        self.Bind(wx.EVT_LISTBOX, self.OnInternalSelect, self.InternalList)
        self.Bind(wx.EVT_LISTBOX, self.OnExternalSelect, self.ExternalList)
        self.Bind(wx.EVT_LISTBOX, self.OnSelectedRegSelect, self.SelectedExtReg)
        self.TruthTable.Bind(wxgrid.EVT_GRID_RANGE_SELECT, self.OnGridSelect)

        self.AnalysisStatusBar.Bind(lib.EVT_STATUS_CHANGED, self.__status_chgd)

        self.Bind(wx.EVT_MENU, self.__tabmgr_factory(self.TruthTablePanel, "Truth Table", self.__window['tt'], self.__refresh_tt), self.__window['tt'])
        self.Bind(wx.EVT_MENU, self.__tabmgr_factory(self.MiniSimPanel, "Condition Testing", self.__window['ct']), self.__window['ct'])
        self.Bind(wx.EVT_MENU, self.__tabmgr_factory(self.ExternalDetails, "External Component Details", self.__window['ec']), self.__window['ec'])
        self.Bind(wx.EVT_MENU, self.__tabmgr_factory(self.GraphPanel, "Component Graph", self.__window['cg']), self.__window['cg'])
        self.Bind(wx.EVT_MENU, self.__tabmgr_factory(self.AnalysisPanel, "Analysis", self.__window['ap']), self.__window['ap'])
        self.Bind(wx.EVT_MENU, self.__tabmgr_factory(self.SimulationPanel, "Run Simulation", self.__window['rs']), self.__window['rs'])
        self.Bind(wx.EVT_MENU, self.__toggle_cp, self.__window['cp'])

        self.Bind(wx.EVT_CLOSE, self.__before_close)

    def __analysis_reset(self, evt):
        self.AnalysisExternalActivity.Reset()
        self.AnalysisDataPoints.SetValue(10)
        self.AnalysisBeginDC.SetValue(100)
        self.AnalysisEndDC.SetValue(800)

    def __pref_analysis_load(self, evt):
        fd = wx.FileDialog(None, wildcard="JungleWalker Preference Files (*.pref)|*.pref")
        result = fd.ShowModal()
        if result == wx.ID_CANCEL:
            return
        try:
            pref = lib.PreferenceLib.Preferences.LoadPrefFile(fd.GetPath())
        except IOError:
            wx.MessageBox("Could not access file.", "I/O Error", wx.OK | wx.ICON_ERROR)
            return
        except lib.PreferenceLib.PreferencesFormatError:
            wx.MessageBox("Invalid preferences file selected.", "File Format Error", wx.OK | wx.ICON_ERROR)
            return
        ptype = pref.GetPreferencesType()
        if ptype == "empty":
            wx.MessageBox("The selected file is empty.", "Info", wx.OK | wx.ICON_INFORMATION)
            return
        if ptype != "Analysis":
            if ptype == "Simulation":
                wx.MessageBox("This preference file is suited for simulation, not analysis.", "Configuration Type Mismatch", wx.OK | wx.ICON_INFORMATION)
                return
            else:
                wx.MessageBox("This preference file is suited for unknown type '%s', not analysis." % ptype, wx.OK | wx.ICON_ERROR)
        env_warnings = []
        environment = pref.GetSection('environment')
        for i in environment.GetKeys():
            if self.AnalysisExternalActivity.HasId(i):
                v1 = min(max(min(environment.GetEntry(i)), 0), 100)
                v2 = min(max(max(environment.GetEntry(i)), 0), 100)
                self.AnalysisExternalActivity.SetRange(i, v1, v2)
            else:
                env_warnings.append(i)
        settings = pref.GetSection('settings')
        if settings.HasEntry('data_points') and settings.EntryIsType('data_points', int):
            self.AnalysisDataPoints.SetValue(settings.GetEntry('data_points'))
        if settings.HasEntry('begin_dc') and settings.EntryIsType('begin_dc', int):
            self.AnalysisBeginDC.SetValue(settings.GetEntry('begin_dc'))
        if settings.HasEntry('end_dc') and settings.EntryIsType('end_dc', int):
            self.AnalysisEndDC.SetValue(settings.GetEntry('end_dc'))
        if len(env_warnings) > 0:
            msg = 'The following external components were defined in the preference file but not found in the model: %s.' % ', '.join(env_warnings)
            wx.MessageBox(msg, 'Warning', wx.OK | wx.ICON_WARNING)

    def __pref_analysis_save(self, evt):
        fd = wx.FileDialog(None, wildcard="JungleWalker Preference Files (*.pref)|*.pref", style=wx.FD_SAVE)
        result = fd.ShowModal()
        if result == wx.ID_CANCEL:
            return
        try:
            f = open(fd.GetPath(), 'w')
        except IOError:
            wx.MessageBox("Could not open file '%s' for writing." % f.GetPath(), "I/O Error", wx.OK | wx.ICON_ERROR)
            return
        p = lib.PreferenceLib.Preferences("Analysis")
        if len(self.AnalysisExternalActivity.GetItemIds()):
            p.CreateSection("environment")
        for i in self.AnalysisExternalActivity.GetItemIds():
            p.SetEntry("environment", i, repr(self.AnalysisExternalActivity.GetRange(i)))
        p.CreateSection("settings")
        p.SetEntry("settings", "data_points", repr(self.AnalysisDataPoints.GetValue()))
        p.SetEntry("settings", "begin_dc", repr(self.AnalysisBeginDC.GetValue()))
        p.SetEntry("settings", "end_dc", repr(self.AnalysisEndDC.GetValue()))
        contents = p.GenerateFile()
        try:
            f.write(contents)
        except IOError:
            wx.MessageBox("Could not write contents to file '%s'." % f.GetPath(), "I/O Error", wx.OK | wx.ICON_ERROR)
        finally:
            f.close()

    def __sim_reset(self, evt):
        self.__mutation_set = {}
        self.ExternalActivity.Reset()

    def __pref_sim_load(self, evt):
        fd = wx.FileDialog(None, wildcard="JungleWalker Preference Files (*.pref)|*.pref")
        result = fd.ShowModal()
        if result == wx.ID_CANCEL:
            return
        try:
            pref = lib.PreferenceLib.Preferences.LoadPrefFile(fd.GetPath())
        except IOError:
            wx.MessageBox("Could not access file.", "I/O Error", wx.OK | wx.ICON_ERROR)
            return
        except lib.PreferenceLib.PreferencesFormatError:
            wx.MessageBox("Invalid preferences file selected.", "File Format Error", wx.OK | wx.ICON_ERROR)
            return
        ptype = pref.GetPreferencesType()
        if ptype == "empty":
            wx.MessageBox("The selected file is empty.", "Info", wx.OK | wx.ICON_INFORMATION)
            return
        if ptype != "Simulation":
            if ptype == "Analysis":
                wx.MessageBox("This preference file is suited for analysis, not simulation.", "Configuration Type Mismatch", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("This preference file is suited for unknown type '%s', not simulation." % ptype, wx.OK | wx.ICON_ERROR)
            return
        
        mut_warnings = []
        mutations = pref.GetSection('mutations')
        self.__mutation_set = {}
        for i in mutations.GetKeys():
            if i in self.env.keys():
                if mutations.EntryIsType(i, int):
                    ge = mutations.GetEntry(i)
                    if ge != 0 and ge != 1:
                        ge = min(1, max(0, ge))
                    self.__mutation_set[i] = str(ge)
            else:
                mut_warnings.append(i)
        env_warnings = []
        environment = pref.GetSection('environment')
        for i in environment.GetKeys():
            if self.ExternalActivity.HasId(i) and environment.EntryIsType(i, int):
                v = min(max(environment.GetEntry(i), 0), 100)
                self.ExternalActivity.SetValue(i, v)
            else:
                env_warnings.append(i)
        if len(mut_warnings) > 0 or len(env_warnings) > 0:
            msg = ""
            if len(mut_warnings):
                msg += 'The following mutations were defined for nodes not present in the model: %s.' % ', '.join(mut_warnings)
            if len(env_warnings):
                msg += 'The following external components either do not exist or were incorrectly implemented in the configuration file: %s.' % ', '.join(env_warnings)
            wx.MessageBox(msg, 'Warning', wx.OK | wx.ICON_WARNING)

    def __pref_sim_save(self, evt):
        fd = wx.FileDialog(None, wildcard="JungleWalker Preference Files (*.pref)|*.pref", style=wx.FD_SAVE)
        result = fd.ShowModal()
        if result == wx.ID_CANCEL:
            return
        try:
            f = open(fd.GetPath(), 'w')
        except IOError:
            wx.MessageBox("Could not open file '%s' for writing." % f.GetPath(), "I/O Error", wx.OK | wx.ICON_ERROR)
            return
        p = lib.PreferenceLib.Preferences("Simulation")
        if len(self.__mutation_set.keys()) > 0:
            p.CreateSection("mutations")
        if len(self.ExternalActivity.GetItemNames()):
            p.CreateSection("environment")
        for i in self.__mutation_set.keys():
            p.SetEntry("mutations", i, self.__mutation_set[i])
        for i in self.ExternalActivity.GetItemIds():
            p.SetEntry("environment", i, self.ExternalActivity.GetValue(i))
        contents = p.GenerateFile()
        try:
            f.write(contents)
        except IOError:
            wx.MessageBox("Could not write contents to file '%s'." % f.GetPath(), "I/O Error", wx.OK | wx.ICON_ERROR)
        finally:
            f.close()
            

    def __toggle_cp(self, evt):
        show = self.__window['cp'].IsChecked()
        self.lbox.Show(show)
        self.__relayout()

    def __config_mutations(self, evt=None):
        md = lib.MutationDialog(None, title="Mutations")
        md.SetupDialog(self.env, self.__mutation_set)
        md.ShowModal()
        self.__mutation_set = md.GetMutationSet()
        md.Destroy()

    # Tab Manager - Private inner class
    class __tabmgr:
        def __init__(self, tabname, panel, tabpane, menuitem, callback):
            self.tn = tabname
            self.pn = panel
            self.tp = tabpane
            self.mi = menuitem
            self.cb = callback
        def manager(self, evt=None):
            on = self.mi.IsChecked()
            if on:
                self.tp.AddPage(self.pn, self.tn)
            else:
                for i in xrange(0, self.tp.GetPageCount()):
                    if self.tp.GetPageText(i) == self.tn:
                        self.tp.RemovePage(i)
                        break
            if callable(self.cb):
                wx.CallAfter(self.cb, self)

    def __tabmgr_factory(self, panel, tabname, menuitem, func=None):
        if func == None:
            func = self.__relayout
        return self.__tabmgr(tabname, panel, self.rbox, menuitem, func).manager

    def __reset_ui(self, clear_graph = False):
        self.InternalList.Clear()
        self.ExternalList.Clear()
        self.ProteinName.SetLabel("No data :(")
        self.TruthTable.ClearTable()
        self.SelectedExt.SetLabel("Nothing loaded :(")
        self.SelectedExtReg.Clear()
        self.ExternalActivity.Clear()
        self.AnalysisExternalActivity.Clear()
        if clear_graph:
            self.CompGraph.Clear()

        for i in xrange(0,self.rbox.GetPageCount()):
            if self.rbox.GetPageText(i) == "Model Simulation":
                sim_win = self.rbox.GetPage(i)
                sim_win.kill_sim()
                self.rbox.DeletePage(i)
            if self.rbox.GetPageText(i) == "Post-Analysis Processing":
                self.rbox.DeletePage(i)
                

    def __close_project(self, evt):
        lib.IDManager.Reset()
        
        self.__reset_ui(True)
        self.appview.Show(False)
        self.waitview.Show()
        self.tb_model.SetLabelText('No Model Loaded.')
        self.__set_load_msg("Select a model to load.")

    def __kill_layout_callback(self, callback):
        self.__layout_callbacks.remove(callback)
        
    def on_sim_over(self, sim):
        self.RunningSim = False
        self.__kill_layout_callback(sim.DoLayout)
        
    def __run_sim(self, evt=None):
        if self.RunningSim:
            self.SimulationStatus.SetLabelText("Simulation already in progress!")
            return
        self.RunningSim = True
        ext_reg = {}
        for i in self.GetComponents():
            if i in self.env.keys():
                continue
            else:
                ext_reg[i] = self.ExternalActivity.GetValue(i)
        sc = lib.SimulationConfig(copy.deepcopy(ext_reg), copy.deepcopy(self.env), copy.deepcopy(self.__mutation_set))
        sim = lib.SimPanel(sc, self, self.SimulationLength.GetValue(), self.__model, self.rbox) # ok, the label "SimulationLength" is deceptive
        self.SimulationStatus.SetLabelText("Starting Simulation.")
        self.rbox.AddPage(sim, "Model Simulation")
        self.rbox.SetSelection(self.rbox.GetPageCount()-1)

        sim.DoLayout()

        sim.Start()

        self.SetSimulator(sim)

        self.__layout_callbacks.append( sim.DoLayout )
        
    def __status_chgd(self, evt):
        self.AnalysisStatusBar.SetProgress(evt.percent)
        if evt.percent < 1.0:
            self.AnalysisStatus.SetText('Analysis at %.0f%%...' % (evt.percent*100))
        if evt.complete and self.AnalysisThread != None:
            self.AnalysisStatus.SetText('Analysis Complete (%.2fs).' % (evt.time / 1000))
            gr = self.AnalysisThread.GetRegulators()

            post_an = lib.PostAnalysisPanel(self.rbox, gr, self.AnalysisThread.GetDataPoints(), self.__model)
            self.rbox.AddPage( post_an, "Post-Analysis Processing" )
            self.rbox.SetSelection( self.rbox.FindPage(post_an) )
            
            self.RunningAnalysis = False
            
    def __run_analysis(self, evt=None):
        if self.RunningAnalysis:
            self.AnalysisStatus.SetText("Analysis already in progress!")
            return
        if self.AnalysisBeginDC.GetValue() > self.AnalysisEndDC.GetValue():
            wx.MessageBox("Data collection start frame cannot exceed data collection end frame!", "Error", wx.OK | wx.ICON_ERROR)
            return
        self.RunningAnalysis = True
        ext_reg = {}
        for i in self.GetComponents():
            if i in self.env.keys():
                continue
            else:
                ext_reg[i] = self.AnalysisExternalActivity.GetIntRange(i)
        f = self.GetFastEnv()
        self.AnalysisThread = lib.AnalysisThread(ext_reg, ext_reg.keys(), f, self.AnalysisDataPoints.GetValue(), self.AnalysisBeginDC.GetValue(),
                                                 self.AnalysisEndDC.GetValue(), self.AnalysisStatusBar)
        self.AnalysisThread.start()

    def OnGridSelect(self, evt):
        self.TruthTable.ClearSelection()

    def OnSelectedRegSelect(self, evt=None):
        nid = self.__extdets_to_node[self.SelectedExtReg.GetSelection()]
        self.InternalList.SetSelection(self.__intlist_to_node.index(nid))
        self.OnInternalSelect()

    def __rewrap_text(self):
        dc = wx.ClientDC(self.rbox)
        dc.SetFont(BIG_FONT)
        l = ''.join(self.ProteinName.GetLabel().split('\n'))
        wrapped = BreakWordWrap(l, self.rbox.GetSize()[0] - (2*RBOX_PADDING), dc)
        self.ProteinName.SetLabel(wrapped)

        l = ''.join(self.SelectedExt.GetLabel().split('\n'))
        wrapped = BreakWordWrap(l, self.ExternalDetails.GetSize()[0], dc)
        self.SelectedExt.SetLabel(wrapped)
        

    def OnExternalSelect(self, evt=None):
        self.ext_prot = self.__extlist_to_node[self.ExternalList.GetSelection()]
        
        dc = wx.ClientDC(self.ExternalDetails)
        dc.SetFont(BIG_FONT)
        wrapped = BreakWordWrap("Factors regulated by %s" % self.__model['speciesMap'][unicode(self.ext_prot)]['name'], self.ExternalDetails.GetSize()[0], dc)
        self.SelectedExt.SetLabel(wrapped)
        self.External_Boxer.Layout()
        self.SelectedExtReg.Clear()

        self.__extdets_to_node = []
        
        for i in self.env.keys():
            p = self.env[i]
            if self.ext_prot in p.regulators:
                self.__extdets_to_node.append(i)
                self.SelectedExtReg.Append(self.__model['speciesMap'][unicode(i)]['name'])

    def __refresh_tt(self, evt=None):
        if self.prot == None:
            self.TruthTable.ClearTable()
            self.ProteinName.SetLabel("")
            return
        prot_name = self.prot.name
        
        dc = wx.ClientDC(self.rbox)
        dc.SetFont(BIG_FONT)
        wrapped = BreakWordWrap("Protein, Gene, or Complex: %s" % prot_name, self.rbox.GetSize()[0] - (2*RBOX_PADDING), dc)
        self.ProteinName.SetLabel(wrapped)
        
        try:
            self.TruthTable.DisplayTable(self.prot)
        except ValueError as ve:
            wx.MessageBox(ve.message, 'Unable to Display Table', wx.OK | wx.ICON_ERROR)
            self.TruthTable.ClearTable()

        self.TruthTablePanel_Boxer.Layout()

    def OnInternalSelect(self, evt=None):
        prot_id = self.__intlist_to_node[self.InternalList.GetSelection()]

        self.prot = self.env[prot_id]

        # Config Condition Tester
        self.MiniSimPanel.ClearLogic()
        self.MiniSimPanel.LoadLogic( self.InternalList.GetStringSelection(), self.prot.regulators, self.prot.TestCondition, self.__model )

        # Refresh Truth Table
        self.__refresh_tt()

    def OnExit(self, evt):
        self.Close()

    def __set_load_msg(self, msg):
        dc = wx.ClientDC(self)
        dc.SetFont(BIG_FONT)
        bww = BreakWordWrap(''.join(msg.split('\n')), self.GetSize()[0] - 20, dc)
        self.loading_lbl.SetLabel(bww)
        self.Refresh()

    def __model_load_ui(self):
        # Init UI
        self.__reset_ui()

        self.__intlist_to_node = []
        self.__extlist_to_node = []
        
        _c = list(self.GetComponents())
        c = []
        for i in _c:
            if i in self.env.keys():
                continue
            else:
                c.append(i)
        c = [(str(self.__model['speciesMap'][nid]['name']), nid) for nid in c]
        c.sort(key=lambda x: x[0].lower())
        for i in c:
            if i == '':
                continue
            self.ExternalList.Append(i[0])
            self.ExternalActivity.Append(i[0], i[1])
            self.AnalysisExternalActivity.Append(i[0], i[1])

            self.__extlist_to_node.append(int(i[1]))
        if len(c) > 0:
            self.ExternalList.SetSelection(0)
            self.OnExternalSelect()

        self.ExternalActivity.SetMinSize((self.ExternalActivity.GetTargetWindow().GetVirtualSize()[0] + 30, 0))
        self.AnalysisExternalActivity.SetMinSize((self.AnalysisExternalActivity.GetTargetWindow().GetVirtualSize()[0] + 20, 0))
        
        k = [(str(self.__model['speciesMap'][nid]['name']), nid) for nid in self.env.keys()]
        k.sort(key=lambda x: x[0].lower())
        for i in k:
            self.InternalList.Append(i[0])
            self.__intlist_to_node.append(i[1])
        if len(self.env.keys()) > 0:
            self.InternalList.SetSelection(0)
            self.OnInternalSelect()

        self.__window['rs'].Check(True)
        if self.rbox.FindPage(self.SimulationPanel) == wx.NOT_FOUND:
            self.rbox.AddPage(self.SimulationPanel, "Run Simulation")
        self.__window['ap'].Check(True)
        if self.rbox.FindPage(self.AnalysisPanel) == wx.NOT_FOUND:
            self.rbox.AddPage(self.AnalysisPanel, "Analysis")

        self.appview.Show(True)
        self.waitview.Show(False)
        self.__relayout()

    def __load_profile(self):
        if isinstance(self.__session, lib.CCApi.AuthSession):
            user = self.__session.GetProfile()
            self.login_item.SetText('Log Out')
            self.lbtn.SetBitmap(self.bmp['logout'])
            self.lbtn.SetToolTip(wx.ToolTip("Log Out"))
            self.tb_username.SetLabel("Logged in as %s" % (user['firstName'] + ' ' + user['lastName']))
            self.tb.Layout()

    def ShowAuthDialog(self, evt):
        if isinstance(self.__session, lib.CCApi.AuthSession):
            # We are already logged in, so the menu item says "Log Out"
            self.__session = lib.CCApi.CCSession()
            self.lbtn.SetBitmap(self.bmp['login'])
            self.lbtn.SetToolTip(wx.ToolTip("Log In"))
            self.tb_username.SetLabel("Logged Out.")
            self.tb.Layout()
            return
        authd = lib.AuthDialog(None)
        res = authd.ShowModal()
        if res == wx.ID_CANCEL:
            return
        authres = self.DoLogIn(authd.GetUsername(), authd.GetPassword())
        if authres == None:
            wx.MessageBox("Successfully logged in.", "Success", wx.ICON_INFORMATION | wx.OK)
        else:
            msg = ""
            if isinstance(authres, lib.CCApi.AuthenticationError):
                msg = "Please ensure that you are using correct credentials."
            elif isinstance(authres, requests.exceptions.ConnectionError):
                msg = "You are not connected to the internet."
            self.tb_username.SetLabel("Log-in failed.")
            wx.MessageBox('Log-in failed. %s' % msg, 'Authentication Error', wx.OK | wx.ICON_ERROR)

    def DoLogIn(self, usr, pwd):
        self.tb_username.SetLabel("Logging in...")
        try:
            prog = wx.ProgressDialog("Logging in...", "Logging into CellCollective...")
            prog.Show()
            prog.Pulse()
            authsess = lib.CCApi.AuthSession.Create(usr, pwd)
            self.__session = authsess
            self.__load_profile()
            prog.Destroy()
            return None
        except lib.CCApi.AuthenticationError as ae:
            return ae
        except requests.exceptions.ConnectionError as ce:
            return ce
        except Exception as e:
            # Some other exception, perhaps handle differently than expected exceptions
            return e

    def ShowModelDialog(self, evt):
        msd = lib.ModelSelectionDialog(self.__session, None)
        res = msd.ShowModal()
        if res == wx.ID_CANCEL:
            return
        mid = msd.GetSelectedModelID()
        if mid[0] == -1:
            return
        
        self.LoadModelById(mid, mid[3])

    def LoadModelById(self, mid, name='Default Model'):
        self.__set_load_msg("Loading Model...")

        m = self.__session.GetModel(mid[0], mid[1], mid[4], mid[2])

        self.appview.Show(False)
        self.waitview.Show()
        self.__relayout()
        t = threading.Thread(target=self.__safe_load_model_data, args=(m,mid[2], name))
        t.start()

    def __safe_load_model_data(self, m, mv, mname):
        """__safe_load_model_data(model, model_version) - runs __load_model_data in a try/except block to catch errors due to bad responses."""
        try:
            self.__load_model_data(m, mv, mname)
        except Exception as e:
            import traceback
            print traceback.format_exc()
            wx.MessageBox('Bad response model data.', 'Bad Response', wx.ICON_ERROR | wx.OK)

    def __load_model_data(self, m, mv, mname):
        # Loading Task
        internal = {}
        external = []

        lib.IDManager.SetModel(m)
        
        self.CompGraph.Clear()

        layoutId = m.get('layoutId', -1)
        layoutMap = m['layoutMap'].get(unicode(layoutId), {})

        self.CompGraph.SetVerticalLimits( layoutMap.get('bottom', -5), layoutMap.get('top', 5) )
        self.CompGraph.SetHorizontalLimits( layoutMap.get('left', -5), layoutMap.get('right', 5) )
        
        layoutNodeMap = m['layoutNodeMap']
        specmap = m['speciesMap']
        regmap = m['regulatorMap']
        condmap = m['conditionMap']
        condspecmap = m['conditionSpeciesMap']
        sc_map = m['subConditionMap']
        scs_map = m['subConditionSpeciesMap']
        dom = m['dominanceMap']

        self.tb_model.SetLabelText(mname)

        self.env = {}
        self.extenv = []

        if layoutMap == {}:
            sg = lib.ConcentricCircleGenerator()
        else:
            sg = None
        
        for i in specmap.keys():
            name = specmap[unicode(i)]['name']
            if not specmap[i]['external']:
                node = lib.CCNode(unicode(i))
                regs = {}
                for n in regmap.keys():
                    entry = regmap[n]
                    if entry['speciesId'] == int(i):
                        regs[n] = (entry['regulationType'], entry.get('conditionRelation', 'OR'), entry['regulatorSpeciesId'])
                for j in regs.keys():
                    if regs[j][0] == "POSITIVE":
                        node.AddPosReg(int(regs[j][2]), int(j), regs[j][1])
                    elif regs[j][0] == "NEGATIVE":
                        node.AddNegReg(int(regs[j][2]), int(j), regs[j][1])
                    # Conditions
                    conds = {}
                    for k in condmap.keys():
                        if condmap[k]['regulatorId'] == int(j):
                            # condition's regulatorId matches that of the current regulator
                            conds[k] = (condmap[k], [])
                    for k in condspecmap.keys():
                        if unicode(condspecmap[k]['conditionId']) in conds.keys():
                            conds[unicode(condspecmap[k]['conditionId'])][1].append(condspecmap[k]['speciesId'])

                    for k in conds.keys():
                        condId = int(k)
                        subconds = {}
                        for sk in sc_map.keys():
                            if sc_map[sk]['conditionId'] == condId:
                                # add subconditions
                                subconds[sk] = (sc_map[sk], [])
                        for sk in scs_map.keys():
                            if unicode(scs_map[sk]['subConditionId']) in subconds.keys():
                                subconds[unicode(scs_map[sk]['subConditionId'])][1].append(scs_map[sk]['speciesId'])
                        scs = []
                        for sk in subconds.keys():
                            subCondId = int(sk)
                            scs.append(subCondId)
                            node.AddSubCondition(condId, subCondId, subconds[sk][0].get('speciesRelation', 'OR'), subconds[sk][0].get('state', 'ON'),
                                                 subconds[sk][0].get('type', 'IF_WHEN'), subconds[sk][1])
                        node.AddCondition( int(j), condId, conds[k][0].get('speciesRelation', 'OR'), conds[k][0].get('subConditionRelation', 'OR'),
                                           conds[k][0].get('state', 'ON'), conds[k][0].get('type', 'IF_WHEN'), conds[k][1], scs)

                    if regs[j][0] == "POSITIVE":
                        for d in dom.keys():
                            if dom[d]['positiveRegulatorId'] == int(j):
                                node.AddDominance( dom[d]['positiveRegulatorId'], dom[d]['negativeRegulatorId'] )
                exp, regids = node.GenerateBooleanExpression(specmap)
                internal[i] = (exp, regids, node)
            else:
                external.append(int(i))
            if sg == None:
                for pos in layoutNodeMap.keys():
                    if layoutNodeMap[pos]['componentId'] == int(i) and layoutNodeMap[pos]['layoutId'] == layoutId:
                        wx.CallAfter(self.CompGraph.AddNode, name, (layoutNodeMap[pos]['x'], layoutNodeMap[pos]['y']), specmap[i]['external'])
                        break
            else:
                p = sg.next()
                wx.CallAfter(self.CompGraph.AddNode, name, (p[0], p[1]), specmap[i]['external'])

        if not sg == None:
            self.CompGraph.SetVerticalLimits( sg.GetBottom(), sg.GetTop() )
            self.CompGraph.SetHorizontalLimits( sg.GetLeft(), sg.GetRight() )
        
        self.extenv = external
        allc = external
        allc.extend(internal.keys())
        for i in internal.keys():
            self.env[i] = lib.Node( str(specmap[unicode(i)]['name']), internal[i][0], internal[i][1], internal[i][2], int(i) )

        # Set our precious model
        self.__model = m
        self.TruthTable.SetModel(self.__model)

        wx.CallAfter(self.__model_load_ui)

    # Auxiliary Functions

    def GetFastEnv(self):
        fenv = {}
        for i in self.env.keys():
            fenv[int(i)] = self.env[i].GetFast()
        return fenv

    def GetComponents(self):
        s = list(self.extenv)
        s.extend(self.env.keys())
        s = [str(i) for i in s] # convert to string from unicode
        return s

def StartJW():
    jw = JungleWalker()
    jw.Show()
    app.MainLoop()

if __name__ == '__main__':
    StartJW()
