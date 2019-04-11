import imp
import os
import threading
import time
import wx

# My own word wrap calculator, because whoever wrote
# wx's is an idiot
WORDWRAP_TOLERANCE = 5
def BreakWordWrap(word, width, dc):
    if word == '':
        return ''
    pieces = word.split(' ')
    if dc.GetTextExtent(pieces[0])[0] > width - WORDWRAP_TOLERANCE:
        return word
    out = ""
    for i in pieces:
        lines = out.split('\n')
        last_line = lines[len(lines)-1]
        if dc.GetTextExtent(last_line + i)[0] > width - WORDWRAP_TOLERANCE:
            out += "\n" + i + " "
        else:
            out += i + " "
    return out

class DiagramPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.__lines = []

        self.Bind(wx.EVT_PAINT, self.__onpaint)
        self.Bind(wx.EVT_SIZE, self.__onresize)

    def AddLine(self, perc_x1, perc_y1, perc_x2, perc_y2):
        self.__lines.append((perc_x1, perc_y1, perc_x2, perc_y2))

    def __onresize(self, evt):
        self.Refresh()

    def __onpaint(self, evt):
        bpdc = wx.PaintDC(self)
        #bpdc.Clear()

        bpdc.SetPen(wx.Pen(wx.BLACK, 3))

        for i in self.__lines:
            sz = self.GetSize()
            if callable(i[0]):
                x1 = i[0]()
            else:
                x1 = sz[0] * i[0]
            if callable(i[1]):
                y1 = i[1]()
            else:
                y1 = sz[1] * i[1]
            if callable(i[2]):
                x2 = i[2]()
            else:
                x2 = sz[0] * i[2]
            if callable(i[3]):
                y2 = i[3]()
            else:
                y2 = sz[1] * i[3]
            bpdc.DrawLine(x1, y1, x2, y2)

class CustomComboBox(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.__items = []
        self.__selected = -1

        self.__lw = wx.PopupTransientWindow(parent.GetTopLevelParent(), wx.SIMPLE_BORDER)
        self.__lb = wx.ListBox(self.__lw)
        lay = wx.BoxSizer(wx.VERTICAL)
        lay.Add( self.__lb, 1, wx.EXPAND )
        self.__lw.SetSizer(lay)
        self.__lw.Hide()

        self.__lb.Bind(wx.EVT_MOTION, self.__lbmotion)
        self.__lb.Bind(wx.EVT_LEFT_DOWN, self.__lbleftdown)

        self.__arrowbox_width = 24

        self.__clicked = False

        self.SetCursor(wx.Cursor( wx.CURSOR_HAND ))
        self.Bind(wx.EVT_PAINT, self.__onpaint)

        self.Bind(wx.EVT_SIZE, lambda evt: self.Refresh())

        self.Bind(wx.EVT_LEFT_DOWN, self.__leftdown)
        self.Bind(wx.EVT_LEFT_UP, self.__leftup)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.__leftwindow)

    # can be implemented by subclasses/instances
    def OnChange(self, chgd_idx):
        pass

    def GetString(self, idx):
        return self.__items[idx]

    def __lbmotion(self, evt):
        item = self.__lb.HitTest(evt.GetPosition())
        if item >= 0:
            self.__lb.SetSelection(item)
        evt.Skip()

    def __lbleftdown(self, evt):
        self.__selected = self.__lb.GetSelection()
        self.__lw.Dismiss()
        self.OnChange(self.__selected)
        self.Refresh()

    def __leftup(self, evt):
        if self.__clicked:
            self.__clicked = False
            # do stuff here
            pos = self.ClientToScreen(self.GetPosition())
            sz  = self.GetSize()
            self.__lw.Position( self.ClientToScreen(0,0), (0, sz[1]) )
            self.__lw.SetMinSize( (sz[0], self.__lb.GetBestSize()[1]) )
            self.__lw.Fit()
            self.__lw.Popup()
        evt.Skip()

    def __leftdown(self, evt):
        self.__clicked = True
        evt.Skip()

    def __leftwindow(self, evt):
        self.__clicked = False
        evt.Skip()

    def __onpaint(self, evt):
        bp_dc = wx.BufferedPaintDC(self)
        try:
            bp_dc = wx.GCDC(bp_dc)
        except:
            # no need to worry, we just won't get aliasing
            pass
        bp_dc.Clear()
        bp_dc.SetPen( wx.Pen( '#cdcdcd', 1 ) )
        bp_dc.SetBrush( wx.Brush('white') )

        box_w = self.GetSize()[0] - self.__arrowbox_width
        box_h = self.GetSize()[1]
        
        bp_dc.DrawRectangle( (0, 0), (box_w, box_h) )
        bp_dc.SetPen( wx.TRANSPARENT_PEN )
        bp_dc.SetBrush( wx.Brush( '#cdcdcd' ) )

        if self.__selected >= 0:
            sel_string = self.__items[self.__selected]
            te = bp_dc.GetTextExtent(sel_string)
            sz = self.GetSize()
            x = max( (box_w / 2) - (te[0] / 2), 5 )
            bp_dc.DrawText(sel_string, x, (sz[1] / 2) - (te[1] / 2))
        
        bp_dc.DrawRectangle( (box_w, 0), (self.__arrowbox_width, box_h) )

        bp_dc.SetPen( wx.Pen('black', 2) )
        bp_dc.DrawLine( box_w + 4, (box_h / 2) - 5, box_w + (self.__arrowbox_width / 2), (box_h / 2) + 5 )
        bp_dc.DrawLine( box_w + (self.__arrowbox_width / 2), (box_h / 2) + 5, box_w + self.__arrowbox_width - 4, (box_h / 2) - 5 )

    def Append(self, item):
        self.__items.append(item)
        self.__lb.Append(item)

    def Clear(self):
        self.__items = []
        self.__lb.Clear()

    def Select(self, ind):
        if ind >= len(self.__items):
            raise ValueError("Index %d out of range!" % ind)
        self.__selected = ind
        self.__lb.SetSelection(ind)
        self.Refresh()

    def GetSelection(self):
        return self.__selected

    def GetStringSelection(self):
        return self.__items[self.__selected]

    def SetStringSelection(self, string):
        i = self.__items.index(string)
        if i == -1:
            return
        else:
            self.__lb.SetSelection(i)

# Convert result set dictionary to CSV text output
def ToCSV( A, precision=1 ):
    ak = A.keys()
    out = ','.join( [str(a) for a in ak] ) + '\n'
    length = len(A[ak[0]])
    lines = []
    prec_str = '%.' + str(precision) + 'f'
    for i in xrange(0, length):
        lines.append(','.join( [prec_str % A[k][i] for k in ak] ))
    out += '\n'.join(lines)
    return out

# Object providing file system access for plug-and-play data processing scripts
class Workspace:
    def __init__(self, ws_dir):
        if not os.path.isdir(ws_dir):
            raise ValueError('Directory does not exist: %s.' % ws_dir)
        self.__dir = ws_dir

    def GetFile(self, name, mode='w'):
        """CreateFile(name, mode='w') - Get the specified file object opened with the specified mode. If the file does not exist and the mode is 'w', the file will
        be created."""
        if ':' in name or '..' in name or '/' in name or '\\' in name:
            raise ValueError('name should not refer to other directories')
        return open(os.path.join(self.__dir, name), mode)

    def GetDirectory(self, subdirectory):
        """GetDirectory(subdirectory) - Create a new Workspace object in the desired subdirectory.
        subdirectory should only be a direct child of the current parent directory. If subdirectory
        does not exist, the directory will be created"""
        if ':' in name or '.' in name or '/' in name or '\\' in name:
            raise ValueError('subdirectory should only be the name of a folder in the directory of this Workspace object!')
        pth = os.path.join( self.__dir, subdirectory)
        if os.path.isdir(pth):
            return Workspace( os.path.join( self.__dir, subdirectory ) )
        else:
            try:
                os.mkdir(subdirectory)
            except OSError:
                return None
            return Workspace( pth )

# Object for storing information about
# data sets and post-analysis operations.
class DataModule:
    def __init__(self, data, workspace_dir, script_console):
        # 'get' is used for B and no others intentionally.
        # B is the only optional data entry, so an error
        # should be triggered if any other entry is missing.
        # However, the data set B is not always necessary, so
        # it is acceptable to be missing set B.
        self.A = data['A']
        self.B = data.get('B')
        self.ExternalA = data['ExternalA']
        self.ExternalB = data.get('ExternalB')
        self.__species_map = data['_species_map']
        self.__species_list = data['_species_list']

        self.__workspace = Workspace(workspace_dir)
        self.__sc = script_console

    def GetInputAData(self):
        return self.ExternalA

    def GetInputBData(self):
        return self.ExternalB

    def GetA(self):
        return self.A

    def GetAllA(self):
        _a = dict(self.A)
        _a.update(self.ExternalA)
        return _a

    def GetEntryA(self, key):
        return self.A[key]

    def GetB(self):
        return self.B

    def GetAllB(self):
        _b = dict(self.B)
        _b.update(self.ExternalB)
        return _b

    def GetEntryB(self, key):
        return self.B[key]

    def GetSpeciesName(self, specId):
        return self.__species_map[unicode(specId)]['name']

    def GetSpeciesList(self):
        if self.__species_list == []:
            tentative = self.A.keys()
        else:
            tentative = self.__species_list

        # eliminate all keys in A that are not in B.
        # The reason we do this is so that datasets
        # generated by other sources (including other
        # models) may be used for analysis tasks. The
        # user will be warned of this, but the program
        # should not break.
        ret = []
        for i in tentative:
            if i in self.B:
                ret.append(i)

        return ret

    def GetWorkspace(self):
        return self.__workspace

    def GetConsole(self):
        return self.__sc

    @staticmethod
    def ToCSV(pydict, precision=1):
        return ToCSV( pydict, precision )

# Class for managing input/output data according
# to internally defined conventions.
class DataSet:
    INPUT_FILE = "inputs.csv"
    OUTPUT_FILE = "outputs.csv"
    
    @staticmethod
    def LoadSet(directory, specmap, by_id=True):
        in_path = os.path.join( directory, DataSet.INPUT_FILE )
        out_path = os.path.join( directory, DataSet.OUTPUT_FILE )
        if not os.path.exists( out_path ) or os.path.isdir( out_path ):
            raise ValueError("Analysis outputs file does not exist or is a directory.")

        try:
            in_file = open(in_path, 'r')
            input_data = in_file.read()
            in_file.close()
        except IOError:
            # file doesn't exist or access is denied
            input_data = None

        try:
            out_file = open(out_path, 'r')
            output_data = out_file.read()
            out_file.close()
        except IOError:
            return (None, "An unexpected I/O error occurred. Be sure that you have read access to the files in the specified directory.")

        do_warning = False
        
        # Process Input Data
        if input_data != None:
            in_lines = input_data.split('\n')
            name_line = in_lines[0]
            in_lines = in_lines[1:]
            try:
                specs = [str(entry) if not by_id else int(entry) for entry in name_line.split(',')]
                specKeys = []

                if not by_id:
                    for key in specs:
                        found = False
                        for _key in specmap.keys():
                            if specmap[_key]['name'] == key:
                                specKeys.append(int(_key))
                                found = True
                                break
                        if not found:
                            # skip this entry, just keep moving.
                            do_warning = True
                            specKeys.append(-1)
                else:
                    specKeys = specs
                        
            except ValueError as e:
                return (None, str(e))
            
            input_data = {}
            for i in in_lines:
                ldata = i.split(',')
                for j in xrange(0, len(ldata)):
                    key = specKeys[j]
                    if key == -1:
                        continue
                    
                    entry = float(ldata[j])
                    if key in input_data.keys():
                        input_data[key].append( entry )
                    else:
                        input_data[key] = [entry]
        else:
            input_data = {}

        # Process Output Data
        out_lines = output_data.split('\n')
        name_line = out_lines[0]
        out_lines = out_lines[1:]

        specs = [str(entry) if not by_id else int(entry) for entry in name_line.split(',')]
        specKeys = []
        if not by_id:
            for key in specs:
                found = False
                for _key in specmap.keys():
                    if specmap[_key]['name'] == key:
                        specKeys.append(int(_key))
                        found = True
                        break
                if not found:
                    do_warning = True
                    specKeys.append(-1)
        else:
            specKeys = specs
                
        output_data = {}

        for i in out_lines:
            ldata = i.split(',')
            for j in xrange(0, len(ldata)):
                key = specKeys[j]
                if key == -1:
                    # skip this
                    continue
                entry = float(ldata[j])
                if key in output_data.keys():
                    output_data[key].append( entry )
                else:
                    output_data[key] = [entry]

        return (input_data, output_data, None) if not do_warning else (input_data, output_data, "Data files contained data for some nodes not included in this model.\
 Be aware that the data in these files may not be compatible with the current model.")

class ScriptConsole(wx.Dialog):
    def __init__(self, parent, title="Post-Analysis Script"):
        wx.Dialog.__init__(self, parent, title=title)

        self.__config_ui()

        self.StartTask()

    def OnClose(self, evt):
        if self.__completed:
            evt.Skip() # only proceed to destroy window if our task is finished

    def __config_ui(self):
        te_pan = wx.Panel( self )
        te_pan.SetBackgroundColour('white')
        self.__te = wx.TextCtrl( te_pan, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH | wx.NO_BORDER )
        f = self.__te.GetFont()
        f.SetWeight(wx.FONTWEIGHT_BOLD)
        self.__te.SetFont(f)
        
        boxs = wx.BoxSizer(wx.VERTICAL)
        boxs.Add(self.__te, 1, wx.EXPAND | wx.ALL, 5)
        te_pan.SetSizer(boxs)

        self.ok_b = wx.Button( self, wx.ID_OK, label="OK" )
        self.ok_b.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        thiss = wx.BoxSizer(wx.VERTICAL)
        thiss.Add( te_pan, 1, wx.EXPAND )
        thiss.Add( self.ok_b, 0, wx.ALL | wx.ALIGN_RIGHT, 10 )
        self.SetSizer(thiss)

        self.SetMinSize((500, 250))
        self.Centre()
        self.Show()

    def WriteRawLine(self, ln):
        if len(self.__te.GetValue()) == 0:
            self.__te.SetValue(ln)
        else:
            self.__te.write('\n' + ln)

    def WriteLine(self, ln):
        self.WriteRawLine('>>> %s' % ln)

    def EndTask(self):
        """EndTask() - Makes it possible to close this dialog after the task related to this dialog has been completed."""
        self.__completed = True
        self.ok_b.Enable()

    def StartTask(self):
        """StartTask() - Make it impossible to close this dialog. Should be followed later by a call to EndTask() to indicate that it is now acceptable to exit."""
        self.__completed = False
        self.ok_b.Disable()

# Meant for doing statistical analysis
# with the data from analysis.
class PostAnalysisPanel(wx.Panel):
    def __init__(self, parent, reglist, datapoints, model):
        wx.Panel.__init__(self, parent)
        self.__regs = reglist
        self.__dpts = datapoints
        self.__model = model

        self.running = False

        self.__config_ui()

        self.__postanalysis = {}
        self.__curmethods = ''
        self.LoadMethodScript('./postanalysis/methods.py', 'Built-in Methods')
        self.SelectModule('Built-in Methods')

    def LoadMethodScript(self, path, modname=None):
        if modname != None and modname in self.__postanalysis.keys():
            raise KeyError('Method Set %s already loaded.' % modname)
        if modname != None:
            module = imp.load_source(modname, path)
        else:
            psplit = os.path.split(path)
            f = psplit[len(psplit)-1].split('.py')[0]
            module = imp.load_source(f, path)
        if modname == None:
            if 'NAME' in dir(module) and type(module.NAME) is str:
                modname = module.NAME
            else:
                psplit = os.path.split(path)
                modname = psplit[len(psplit)-1]
            if modname in self.__postanalysis.keys():
                raise KeyError('Method Set %s already loaded.' % modname)
        if 'REGISTER' in dir(module) and type(module.REGISTER) is dict:
            self.__postanalysis[modname] = {}
            for i in module.REGISTER.keys():
                try:
                    if callable(module.REGISTER[i][0]):
                        self.__postanalysis[modname][i] = module.REGISTER[i]
                except TypeError as te:
                    del self.__postanalysis[modname] # need to get this out of the way, but then we can continue error propagation
                    raise te
            self.script_src.Append(modname)
            return modname
        else:
            if not 'REGISTER' in dir(module):
                raise AttributeError('Post-Analysis method must contain a REGISTER dictionary associating analysis method names with functions.')
            else:
                raise TypeError('REGISTER variable in post-analysis method script must be a dictionary associating analysis method names with functions.')

    def SelectModule(self, modname, chg_script_src=True):
        if not modname in self.__postanalysis.keys():
            raise KeyError('No module loaded with name \'%s\'.' % modname)
        self.__curmethods = modname
        if chg_script_src:
            self.script_src.SetStringSelection(modname)
        self.method_box.Clear()
        for i in self.__postanalysis[modname].keys():
            self.method_box.Append(i)
        if len(self.__postanalysis[modname]) > 0:
            self.method_box.Select(0)
            meth = self.__postanalysis[modname][self.method_box.GetStringSelection()]
            if meth[1]:
                self.dataset_loc.Enable()
            else:
                self.dataset_loc.Disable()

    def ChgModule(self, evt):
        self.SelectModule( self.script_src.GetStringSelection(), False )

    def __config_ui(self):
        main_pan = wx.Panel(self)
        box_1 = wx.Panel(main_pan)
        box_2 = DiagramPanel(main_pan)
        box_3 = wx.Panel(main_pan)
        box_4 = DiagramPanel(main_pan)
        box_5 = wx.Panel(main_pan)

        sim_lbl_panel = wx.Panel(box_1, style=wx.SIMPLE_BORDER)
        sim_lbl = wx.StaticText( sim_lbl_panel, label="Input Data Set (Set A)", style=wx.ALIGN_CENTRE_HORIZONTAL )
        sim_boxer = wx.BoxSizer(wx.VERTICAL)
        sim_boxer.AddStretchSpacer(2)
        sim_boxer.Add(sim_lbl, 1, wx.EXPAND)
        sim_boxer.AddStretchSpacer(2)
        sim_lbl_panel.SetSizer(sim_boxer)
        
        dataset = wx.Panel(box_1, style=wx.SIMPLE_BORDER)
        lab_data_lbl = wx.StaticText( dataset, label="External Data Set (Set B)" )
        self.dataset_loc = wx.DirPickerCtrl(dataset)
        self.dataset_loc.GetTextCtrl().Disable()
        dataset_boxer = wx.BoxSizer(wx.VERTICAL)
        dataset_boxer.Add(lab_data_lbl, 1, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 20)
        dataset_boxer.Add(self.dataset_loc, 1, wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, 20)
        dataset.SetSizer(dataset_boxer)

        def __onresize(evt=None):
            sim_lbl_sz = (box_1.GetSize()[0] - 40, sim_lbl_panel.GetBestSize()[1])
            sim_lbl_panel.SetMinSize( sim_lbl_sz )
            sim_lbl_panel.SetMaxSize( sim_lbl_sz )
            dataset_sz = (box_1.GetSize()[0] - 40, dataset.GetBestSize()[1])
            dataset.SetMinSize( dataset_sz )
            dataset.SetMaxSize( dataset_sz )

            if evt != None:
                evt.Skip()
            
        box_1.Bind(wx.EVT_SIZE, __onresize)
        
        box_1_sizer = wx.BoxSizer(wx.VERTICAL)
        box_1_sizer.AddStretchSpacer(1)
        box_1_sizer.Add( sim_lbl_panel, 0, wx.ALIGN_RIGHT )
        box_1_sizer.AddStretchSpacer(1)
        box_1_sizer.Add( dataset, 0, wx.ALIGN_RIGHT )
        box_1_sizer.AddStretchSpacer(1)
        box_1.SetSizer(box_1_sizer)

        TOP_PERC = lambda: ( sim_lbl_panel.GetPosition()[1] + (sim_lbl_panel.GetSize()[1] / 2) )
        BOTTOM_PERC = lambda: ( dataset.GetPosition()[1] + (dataset.GetSize()[1] / 2) )
        box_2.AddLine( 0, TOP_PERC, 0.5, TOP_PERC )
        box_2.AddLine( 0, BOTTOM_PERC, 0.5, BOTTOM_PERC )
        box_2.AddLine( 0.5, TOP_PERC, 0.5, BOTTOM_PERC )
        box_2.AddLine( 0.5, 0.5, 1, 0.5 )

        self.method_box = CustomComboBox(box_3)
        def meth_chg(idx):
            string = self.method_box.GetString(idx)
            meth = self.__postanalysis[self.__curmethods][string]
            if meth[1]:
                self.dataset_loc.Enable()
            else:
                self.dataset_loc.Disable()
        self.method_box.OnChange = meth_chg

        box_3_sizer = wx.BoxSizer(wx.VERTICAL)
        box_3_sizer.AddStretchSpacer( 3 )
        box_3_sizer.Add( self.method_box, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND )
        box_3_sizer.AddStretchSpacer( 3 )
        box_3.SetSizer(box_3_sizer)

        box_4.AddLine( 0, 0.5, 1, 0.5 )

        process_btn = wx.Button(box_5, label="Run ->")
        process_btn.Bind( wx.EVT_BUTTON, self.__on_run )
        process_btn.Disable()
        box_5_sizer = wx.BoxSizer(wx.VERTICAL)
        box_5_sizer.AddStretchSpacer( 1 )
        box_5_sizer.Add( process_btn, 0 )
        box_5_sizer.AddStretchSpacer( 1 )
        box_5.SetSizer(box_5_sizer)

        pa_size = wx.BoxSizer(wx.HORIZONTAL)
        pa_size.AddStretchSpacer( 1 )
        pa_size.Add( box_1, 6, wx.EXPAND )
        pa_size.Add( box_2, 2, wx.EXPAND )
        pa_size.Add( box_3, 4, wx.EXPAND )
        pa_size.Add( box_4, 2, wx.EXPAND )
        pa_size.Add( box_5, 2, wx.EXPAND )
        pa_size.AddStretchSpacer( 1 )
        
        main_pan.SetSizer(pa_size)

        # top bar
        top_bar = wx.Panel(self, style=wx.SIMPLE_BORDER)
        script_src_lbl = wx.StaticText(top_bar, label="Script Source:")
        self.script_src = wx.Choice(top_bar)
        import_btn = wx.Button(top_bar, label="Import Script Source...")
        
        bmp_quit = wx.BitmapButton( top_bar, bitmap=wx.ArtProvider.GetBitmap(wx.ART_QUIT), size=(32, 32) )
        bmp_quit.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        bmp_quit.SetToolTip(wx.ToolTip("Quit Post-Analysis"))

        # bind the quitter!!!
        def end_post_analysis(evt):
            p = self.GetParent()
            p.RemovePage(p.FindPage(self))
            self.Destroy()
        self.Bind(wx.EVT_BUTTON, end_post_analysis, bmp_quit)

        self.script_src.Bind(wx.EVT_CHOICE, self.ChgModule)

        top_bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_bar_sizer.Add( script_src_lbl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10 )
        top_bar_sizer.Add( self.script_src, 0, wx.TOP | wx.BOTTOM | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10 )
        top_bar_sizer.Add( import_btn, 0, wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, 10 )
        top_bar_sizer.AddStretchSpacer(1)
        top_bar_sizer.Add( bmp_quit, 0, wx.ALL, 10 )
        top_bar.SetSizer(top_bar_sizer)

        def do_import(evt):
            fd = wx.FileDialog(None, wildcard="Python Scripts (.py)|*.py")
            fd.ShowModal()
            if fd.GetPath() == '':
                return
            pyfile = fd.GetPath()
            try:
                mod = self.LoadMethodScript( pyfile )
                self.SelectModule( mod )
            except KeyError as ke:
                wx.MessageBox(ke.message, 'Import Error', wx.ICON_ERROR | wx.OK)
            except AttributeError as ae:
                wx.MessageBox(ae.message, 'Import Error', wx.ICON_ERROR | wx.OK)
            except TypeError as te:
                wx.MessageBox(te.message, 'Import Error', wx.ICON_ERROR | wx.OK)
            except IOError:
                wx.MessageBox('Could not access the selected file.', 'Import Error', wx.ICON_ERROR | wx.OK)

        self.Bind(wx.EVT_BUTTON, do_import, import_btn)

        # bottom bar
        bottom_bar = wx.Panel(self, style=wx.SIMPLE_BORDER)
        output_lbl = wx.StaticText(bottom_bar, label="Output Directory:")
        self.output_fp  = wx.DirPickerCtrl(bottom_bar)
        self.output_fp.GetTextCtrl().Disable()

        sep = wx.StaticLine(bottom_bar, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_VERTICAL)

        interp_str_label = wx.StaticText(bottom_bar, label="Input CSV identifies nodes by name (i.e. instead of by CellCollective's ID number)?")
        self.interp_str       = wx.CheckBox(bottom_bar)
        self.interp_str.SetValue(True)

        def do_enable(evt):
            if self.output_fp.GetPath() != '':
                process_btn.Enable()
            
        self.output_fp.Bind( wx.EVT_DIRPICKER_CHANGED, do_enable )

        bottom_bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bottom_bar_sizer.AddStretchSpacer( 1 )
        bottom_bar_sizer.Add( output_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT )
        bottom_bar_sizer.Add( self.output_fp, 2, wx.EXPAND | wx.ALL, 10 )
        bottom_bar_sizer.Add( sep, 0, wx.ALL | wx.EXPAND, 10 )
        bottom_bar_sizer.Add( interp_str_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT )
        bottom_bar_sizer.Add( self.interp_str, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10 )
        bottom_bar_sizer.AddStretchSpacer( 1 )
        bottom_bar.SetSizer(bottom_bar_sizer)

        # sizer for self
        self_sizer = wx.BoxSizer(wx.VERTICAL)
        self_sizer.Add(top_bar, 0, wx.EXPAND)
        self_sizer.Add(main_pan, 1, wx.EXPAND)
        self_sizer.Add(bottom_bar, 0, wx.EXPAND)
        self.SetSizer(self_sizer)

    def __load_dataset_and_execute(self, pth, model, by_id, sc, proc_meth, output_folder):
        result = DataSet.LoadSet( pth, model, by_id )

        sc.WriteRawLine("External data set loaded. Running script...")
        sc.WriteRawLine("")

        # Did an error occur?
        if result[0] == None:
            sc.WriteRawLine('FATAL ERROR: %s' % result[1])
            return

        b_in, b_out, warning = result
        if warning != None:
            sc.WriteRawLine('WARNING: %s' % warning)

        apply( proc_meth, (DataModule( {'A' :self.__dpts[0], 'ExternalA': self.__dpts[1], 'B': b_out, 'ExternalB': b_in, '_species_map': self.__model['speciesMap'],
                                            '_species_list': []}, output_folder, sc),) )

        self.running = False
        sc.EndTask()
        sc.WriteRawLine("")
        sc.WriteRawLine("Script executed.")


    def __on_run(self, evt):
        if self.running:
            return

        self.running = True

        meth = self.method_box.GetStringSelection()
        method = self.__postanalysis[self.__curmethods][meth]

        output_folder = self.output_fp.GetPath()
        if not os.path.isdir(output_folder):
            wx.MessageBox('Output folder does not exist: %s.' % output_folder, 'Output Error', wx.ICON_ERROR | wx.OK)
            return
        
        if method[1]: # second item of tuple determines whether method is unary or binary
            sc = ScriptConsole( self.GetTopLevelParent(), meth )
            sc.WriteRawLine("Loading external data set...")

            t = threading.Thread( target=self.__load_dataset_and_execute, args=(self.dataset_loc.GetPath(), self.__model['speciesMap'], not self.interp_str.GetValue(),
                                                                                    sc, method[0], output_folder) )
            t.start()
        else:
            sc = ScriptConsole( self.GetTopLevelParent(), meth )
            sc.WriteRawLine("Running script...")
            sc.WriteRawLine("")
            
            apply( method[0], (DataModule( {'A': self.__dpts[0], 'ExternalA': self.__dpts[1], '_species_map': self.__model['speciesMap'], '_species_list': []},
                                           output_folder, sc ),) )
            self.running = False
            sc.EndTask()
            sc.WriteRawLine("")
            sc.WriteRawLine("Script executed.")
