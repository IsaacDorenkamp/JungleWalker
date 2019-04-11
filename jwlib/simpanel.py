import math
import threading
import time
import wx

import dialogs

from dialogs import *
from jwaux import *
from modellib import *

class SimPanel(wx.Panel):
    def __init__(self, sim_config, jw, sim_speed, model, *args, **kwargs):
        """SimPanel(simulation_config, *args, **kwargs)
        A Panel used to run simulations. Simulation is configured with
        the specified sim_config object which specifies the external
        regulators, internal environment, and mutation set. The panel
        GUI object is configured by the *args and **kwargs. Pass in an
        integer to the kwarg 'sim_speed' to set the minimum length of a
        simulation step. The default is 50 milliseconds."""
        wx.Panel.__init__(self, *args, **kwargs)

        self.__jw = jw # needed for after the sim is killed

        # The bitmaps in question absolutely SHOULD NOT be missing. If they are, however,
        # we will use empty bitmaps to prevent the program from breaking at this point.
        try:
            play_bmp  = wx.Bitmap("./img/play.bmp", wx.BITMAP_TYPE_ANY)
        except:
            play_bmp = wx.Bitmap(28, 28)
            
        try:
            pause_bmp = wx.Bitmap("./img/pause.bmp", wx.BITMAP_TYPE_ANY)
        except:
            pause_bmp = wx.Bitmap(28, 28)

        playmask  = wx.Mask(play_bmp, wx.WHITE)
        pausemask = wx.Mask(pause_bmp, wx.WHITE)

        play_bmp.SetMask(playmask)
        pause_bmp.SetMask(pausemask)

        self.PLAY_BMP = play_bmp
        self.PAUSE_BMP = pause_bmp

        self.__simulation_step = sim_speed

        self.__simulation = Simulation(sim_config.ExternalRegulators, sim_config.InternalEnvironment, sim_config.MutationSet)

        self.__analysis = {}
        for i in self.__simulation.GetInternalComponents().keys():
            self.__analysis[int(i)] = 0

        self.Running = False
        self.Finished = False
        self.__lists = {}

        # Simulation Control
        self.paused = True
        self.__do_restart = False

        self.__do_next = False
        self.__do_prev = False

        # Threading Stuff
        self.__sim_lock = threading.Lock()
        self.__analysis_lock = threading.Lock()
        self.__pause_lock = threading.Lock()
        self.__running_lock = threading.Lock()

        self.can_kill = None
        self.thread = None

        self.__model = model

        self.__tree_to_node = {}

        self.__config_ui()

    def __toggle_pause(self, evt=None):
        with self.__pause_lock:
            if self.paused:
                self.pauser.SetBitmap(self.PAUSE_BMP)
                self.pauser.SetToolTip(wx.ToolTip("Pause the Simulation"))
            else:
                self.pauser.SetBitmap(self.PLAY_BMP)
                self.pauser.SetToolTip(wx.ToolTip("Run the Simulation"))
            self.paused = not self.paused

    def __config_ui(self):
        self.ComponentTree = wx.TreeCtrl(self)
        self.ViewPanel = wx.Panel(self)

        erv = self.__simulation.GetExternalRegulators()

        self.Root = self.ComponentTree.AddRoot("Components")

        self.ExternalTree = self.ComponentTree.AppendItem(self.Root, "External Components")

        ek = erv.keys()
        ek.sort(key=str.lower)

        self.__tree_ext = {}
        for i in ek:
            self.__tree_ext[i] = (self.ComponentTree.AppendItem(self.ExternalTree, "%s: %d%%" % (self.__model['speciesMap'][i]['name'], erv[i])),
                                  self.__mode['speciesMap'][i]['name'])

        self.InternalTree = self.ComponentTree.AppendItem(self.Root, "Internal Components")
        self.InternalTreeItems = {}

        env = self.__simulation.GetEnvironment()
        enk = [(self.__model['speciesMap'][k]['name'], k) for k in env.keys()]
        enk.sort(key=lambda x: x[0].lower())
        
        for i in enk:
            self.InternalTreeItems[i[1]] = self.ComponentTree.AppendItem(self.InternalTree, i[0])
            self.__tree_to_node[self.InternalTreeItems[i[1]]] = env[i[1]]

        self.ListTree = self.ComponentTree.AppendItem(self.Root, 'Lists')
        self.ComponentTree.Expand(self.Root)

        bx = wx.BoxSizer(wx.HORIZONTAL)

        bx.Add(self.ComponentTree, 0, wx.EXPAND)
        bx.Add(self.ViewPanel, 1, wx.EXPAND)

        self.SetSizer(bx)

        # ViewPanel Stuff
        self.__tb = wx.Panel(self.ViewPanel, wx.ID_ANY)
        newlist = wx.BitmapButton(self.__tb, wx.ID_NEW, wx.ArtProvider.GetBitmap(wx.ART_NEW))
        newlist.SetToolTip(wx.ToolTip('New List'))
        self.pauser = wx.BitmapButton(self.__tb, wx.ID_ANY, self.PLAY_BMP)
        self.pauser.SetToolTip(wx.ToolTip('Run the Simulation')) # The simulation begins in the paused state
        self.logic_edit = wx.BitmapButton(self.__tb, wx.ID_ANY, wx.ArtProvider.GetBitmap(wx.ART_LIST_VIEW))
        self.logic_edit.SetToolTip(wx.ToolTip('Edit Regulation Mechanism Logic'))
        tracker = wx.BitmapButton(self.__tb, wx.ID_ANY, wx.ArtProvider.GetBitmap(wx.ART_HELP_BOOK))
        tracker.SetToolTip(wx.ToolTip('Tracked Proteins'))
        restart_sim = wx.BitmapButton(self.__tb, wx.ID_ANY, wx.ArtProvider.GetBitmap(wx.ART_UNDO))
        restart_sim.SetToolTip(wx.ToolTip('Restart Simulation'))
        back_frame = wx.BitmapButton(self.__tb, wx.ID_ANY, wx.ArtProvider.GetBitmap(wx.ART_GO_BACK))
        back_frame.SetToolTip(wx.ToolTip('Previous Frame'))
        self.__sim_steps = wx.StaticText(self.__tb, wx.ID_ANY, label="Frames 0-100")
        next_frame = wx.BitmapButton(self.__tb, wx.ID_ANY, wx.ArtProvider.GetBitmap(wx.ART_GO_FORWARD))
        next_frame.SetToolTip(wx.ToolTip('Next Frame'))
        doquit = wx.BitmapButton(self.__tb, wx.ID_ANY, wx.ArtProvider.GetBitmap(wx.ART_QUIT))
        doquit.SetToolTip(wx.ToolTip('Quit Simulation'))

        SIZE=(36, 36)
        newlist.SetMinSize(SIZE)
        self.pauser.SetMinSize(SIZE)
        self.logic_edit.SetMinSize(SIZE)
        tracker.SetMinSize(SIZE)
        restart_sim.SetMinSize(SIZE)
        doquit.SetMinSize(SIZE)
        back_frame.SetMinSize(SIZE)
        next_frame.SetMinSize(SIZE)

        tbsizer = wx.BoxSizer(wx.HORIZONTAL)

        tbsizer.Add(newlist, 0, wx.ALL, border=5)
        tbsizer.Add(self.pauser, 0, wx.ALL, border=5)
        tbsizer.Add(self.logic_edit, 0, wx.ALL, border=5)
        tbsizer.Add(tracker, 0, wx.ALL, border=5)
        tbsizer.Add(restart_sim, 0, wx.ALL, border=5)
        tbsizer.Add(back_frame, 0, wx.ALL, border=5)
        tbsizer.Add(self.__sim_steps, 0, wx.ALL | wx.ALIGN_CENTER, border=5)
        tbsizer.Add(next_frame, 0, wx.ALL, border=5)
        tbsizer.AddStretchSpacer()
        tbsizer.Add(doquit, 0, wx.ALL, border=5)

        self.__tb.SetSizer(tbsizer)

        self.Monitor = wx.Panel(self.ViewPanel)
        
        self.Viewing = wx.ListCtrl(self.Monitor, style=wx.LC_REPORT)
        self.Viewing.AppendColumn('Component Name')
        self.Viewing.AppendColumn('Activity Level')
        self.Viewing.SetColumnWidth(0, 115)
        self.Viewing.SetColumnWidth(1, 85)

        self.__viewdata = {} # This is used to help associate the Viewing list items with Node objects

        self.ActMonitor = ActivityMonitor(self.Monitor)

        monitorsizer = wx.BoxSizer(wx.HORIZONTAL)

        monitorsizer.Add(self.Viewing, 0, wx.EXPAND)
        monitorsizer.Add(self.ActMonitor, 1, wx.EXPAND)

        self.Monitor.SetSizer(monitorsizer)

        vpbx = wx.BoxSizer(wx.VERTICAL)

        vpbx.Add(self.__tb, 0, wx.EXPAND)
        vpbx.Add(self.Monitor, 1, wx.EXPAND)
        self.ViewPanel.SetSizer(vpbx)

        # popup menu
        self.__popup = wx.Menu()
        
        editlist = self.__popup.Append(wx.ID_ANY, "Edit")
        rmvlist  = self.__popup.Append(wx.ID_ANY, "Delete")

        # Configure Events
        self.Bind(wx.EVT_BUTTON, self.__new_list, newlist)
        self.Bind(wx.EVT_BUTTON, self.__toggle_pause, self.pauser)
        self.Bind(wx.EVT_BUTTON, self.__edit_logic, self.logic_edit)
        self.Bind(wx.EVT_MENU, self.__edit_list, editlist)
        self.Bind(wx.EVT_MENU, self.__rmv_list, rmvlist)
        self.Bind(wx.EVT_BUTTON, self.__show_tracklist, tracker)
        self.Bind(wx.EVT_BUTTON, self.__restart_sim, restart_sim)
        self.Bind(wx.EVT_BUTTON, self.kill_sim, doquit)
        self.Bind(wx.EVT_BUTTON, self.__prev_frame, back_frame)
        self.Bind(wx.EVT_BUTTON, self.__next_frame, next_frame)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.__list_track_menu, self.Viewing)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.__change_list, self.ComponentTree)
        self.Bind(wx.EVT_TREE_ITEM_MENU, self.__do_popup, self.ComponentTree)

    def __prev_frame(self, evt):
        self.__do_prev = True

    def __next_frame(self, evt):
        self.__do_next = True

    def __restart_sim(self, evt):
        self.__do_restart = True

    def kill_sim(self, evt=None):
        with self.__running_lock:
            self.Running = False
        while not self.Finished:
            time.sleep(.005)
        p = self.GetParent()
        p.RemovePage(p.FindPage(self))
        self.__jw.on_sim_over(self)
        self.Destroy()

    def __show_tracklist(self, evt):
        td = TrackListDialog(self.ActMonitor, None, title="Tracked Proteins")
        td.ShowModal()
        td.Destroy()

    def __list_track_menu(self, evt):
        s = self.__lists[self.__displaying][4][self.Viewing.GetNextSelected(-1)]
        if s == None:
            return
        self.__do_track_menu(s)

    def __edit_logic(self, evt):
        sel = self.Viewing.GetNextSelected(-1)
        if sel >= 0:
            le = LogicEditor(self.__model, None, title="Logic Editor")
            le.LoadLogic(self.__viewdata[sel])
            res = le.ShowModal()
            if res == wx.ID_OK:
                # apply changes
                self.__viewdata[sel].ConformToCCNode(le.GetCCNode(), self.__model['speciesMap'])

                # add new regulators etc. to model
                le.GetCCNode().AppropriateNewData(self.__model)
            le.Destroy()
        else:
            wx.MessageBox("No node selected!", "No Selection", wx.OK | wx.ICON_ERROR)

    def __rmv_list(self, evt):
        seltxt = self.ComponentTree.GetItemText(self.ComponentTree.GetSelection())
        self.RemoveList(seltxt)

    def __do_popup(self, evt):
        # return if nothing is actually selected
        sel = self.ComponentTree.GetSelection()
        if not sel.IsOk():
            return
        seltxt = self.ComponentTree.GetItemText(sel)
        if self.ComponentTree.GetItemParent(sel) == self.ListTree and self.__lists[seltxt][3]: # ensure that selected list is mutable
            self.PopupMenu( self.__popup )
        if self.ComponentTree.GetItemParent(sel) == self.InternalTree:
            self.__do_tree_menu(sel)

    def __do_tree_menu(self, sel):
        txt = str(self.ComponentTree.GetItemText(sel))
        track_popup = wx.Menu()
        if txt in self.ActMonitor.GetTracking():
            item = track_popup.Append(wx.ID_ANY, "Stop Tracking")
            def __st(evt):
                node = self.__tree_to_node.get(sel)
                if node == None:
                    return
                with self.ActMonitor.ThreadLock:
                    self.ActMonitor.UnTrack(node)
            self.Bind(wx.EVT_MENU, __st, item)
        else:
            item = track_popup.Append(wx.ID_ANY, "Track %s" % txt)
            def __st(evt):
                c = wx.ColourDialog(None)
                c.SetTitle("Select Graph Color")
                c.Centre()
                result = c.ShowModal()
                if result == wx.ID_CANCEL:
                    return
                node = self.__tree_to_node.get(sel)
                if node == None:
                    return
                with self.ActMonitor.ThreadLock:
                    self.ActMonitor.Track(node, c.GetColourData().GetColour().GetAsString())
            self.Bind(wx.EVT_MENU, __st, item)
        if len(self.__lists) > 0:
            def __add_to_list(evt):
                sld = SelectListDialog(None, title="Add %s to list" % txt)
                sld.SetLists(self.__lists.keys())
                sld.ShowModal()
                l = sld.GetList()
                node = self.__tree_to_node.get(sel)
                if node == None:
                    # what the heck? don't do anything, I guess
                    return
                if l == '':
                    return
                if node in self.__lists[l][4]:
                    wx.MessageBox('%s is already in list %s!' % (txt, l), 'Error', wx.OK | wx.ICON_ERROR)
                    return
                self.ListAppend(l, txt, node)
            list_add = track_popup.Append(wx.ID_ANY, "Add %s to a list" % txt)
            self.Bind(wx.EVT_MENU, __add_to_list, list_add)
            
        self.PopupMenu(track_popup)

    def __do_track_menu(self, node):
        txt = str(node.name)
        track_popup = wx.Menu()
        if node in self.ActMonitor.GetTracking():
            item = track_popup.Append(wx.ID_ANY, "Stop Tracking")
            def __st(evt):
                with self.ActMonitor.ThreadLock:
                    self.ActMonitor.UnTrack(node)
            self.Bind(wx.EVT_MENU, __st, item)
        else:
            item = track_popup.Append(wx.ID_ANY, "Track %s" % txt)
            def __st(evt):
                c = wx.ColourDialog(None)
                c.SetTitle("Select Graph Color")
                c.Centre()
                result = c.ShowModal()
                if result == wx.ID_CANCEL:
                    return
                with self.ActMonitor.ThreadLock:
                    self.ActMonitor.Track(node, c.GetColourData().GetColour().GetAsString())
            self.Bind(wx.EVT_MENU, __st, item)
        self.PopupMenu(track_popup)

    def __new_list(self, evt=None):
        specmap = self.__model['speciesMap']
        
        ld = ListManager(None, title="New Component List")
        ic = self.__simulation.GetInternalComponents()
        ick = ic.keys()
        ick.sort(key=lambda x: self.__model['speciesMap'][x]['name'].lower())
        for i in ick:
            ld.Append(specmap[i]['name'])
            ld.SetData( ld.GetItemCount()-1, ic[i] )
        result = ld.ShowModal()
        if result == wx.ID_CANCEL:
            return
        nm = ld.GetName()
        if nm in self.__lists.keys():
            wx.MessageBox('List with name %s already exists.' % nm, 'Error', wx.OK | wx.ICON_ERROR)
            ld.Destroy()
            return
        chckd = ld.GetCheckedItems()
        self.AddList(nm)
        for i in chckd:
            self.ListAppend(nm, ld.GetData(i).name, ld.GetData(i))
        ld.Destroy()

    def __edit_list(self, evt):
        sel = self.ComponentTree.GetSelection()
        specmap = self.__model['speciesMap']
        if self.ComponentTree.GetItemParent(sel) == self.ListTree:
            lm = ListManager(None, title="Edit List")
            txt = self.ComponentTree.GetItemText(sel)
            ic = self.__simulation.GetInternalComponents()
            ick = ic.keys()
            ick.sort(key=lambda x: specmap[x]['name'].lower())
            for i in ick:
                lm.Append(specmap[i]['name'])
                lm.SetData( lm.GetItemCount()-1, ic[i] )
            lm.SetName(txt)
            
            for i in self.__lists[txt][4]:
                item_ind = lm.GetIndexByData(i)
                if item_ind == -1:
                    continue
                lm.SetChecked( item_ind )
                
            result = lm.ShowModal()
            if result == wx.ID_CANCEL:
                return
            nm = lm.GetName()
            chckd = lm.GetCheckedItems()
            if nm != txt:
                self.RemoveList(txt)
                self.AddList(nm)
                for i in chckd:
                    self.ListAppend(nm, i)
                self.__select_list(nm)
            else:
                ci = []
                for i in chckd:
                    ci.append(lm.GetData(i))
                
                for i in chckd:
                    data = lm.GetData(i)
                    if not self.InList(nm, data):
                        self.ListAppend(nm, data.name, data)
                lst = list(self.__lists[nm][4]) # copy the list, because we delete items from the actual list as we go along and this would affect iteration.
                for i in lst:
                    if not i in ci:
                        self.ListRemove(nm, i)
                self.__change_list()
            
            lm.Destroy()

    def __change_list(self, evt=None):
        s = self.ComponentTree.GetSelection()
        parent = self.ComponentTree.GetItemParent(s)
        if parent == self.ListTree:
            self.__display_list(self.ComponentTree.GetItemText(s))

    def __display_list(self, lname):
        if not lname in self.__lists.keys():
            # Really bad :(
            wx.MessageBox("An unexpected internal error occurred.", "Internal Error", wx.OK | wx.ICON_ERROR)
            return
        self.__displaying = lname
        self.Viewing.ClearAll()
        self.__viewdata = {}
        
        self.Viewing.AppendColumn('Component Name')
        self.Viewing.AppendColumn('Activity Level')
        self.Viewing.SetColumnWidth(0, 115)
        self.Viewing.SetColumnWidth(1, 85)
        lst = self.__lists[lname][4]
        with self.__analysis_lock:
            for i in xrange(0, len(lst)):
                self.Viewing.Append((lst[i].name, "%.0f%%" % self.__analysis[lst[i].speciesId]))
                self.__viewdata[self.Viewing.GetItemCount()-1] = lst[i]

    def __select_list(self, nm):
        item = self.__lists[nm][1]
        self.ComponentTree.SelectItem(item)
        self.__change_list()

    def AddList(self, name, mutable=True):
        if name in self.__lists.keys():
            wx.MessageBox("List with name %s already exists." % name, "Error", wx.ICON_ERROR | wx.OK)
            return
        self.__lists[name] = ([], self.ComponentTree.AppendItem(self.ListTree, name), [], mutable, [])
        if len(self.__lists) == 1:
            self.ComponentTree.Expand(self.ListTree)

    def ListAppend(self, name, prot, prot_obj):
        if not name in self.__lists.keys():
            raise ValueError("No list %s exists in SimPanel." % name)
        self.__lists[name][0].append(prot)
        self.__lists[name][2].append(self.ComponentTree.AppendItem(self.__lists[name][1], prot))
        self.__lists[name][4].append(prot_obj)
        self.__display_list(name)

    def ListRemove(self, name, prot_obj):
        if not name in self.__lists.keys():
            raise ValueError("No list %s exists in SimPanel." % name)
        for i in xrange(0, len(self.__lists[name][0])):
            if self.__lists[name][4][i] == prot_obj:
                del self.__lists[name][0][i]
                self.ComponentTree.Delete(self.__lists[name][2][i])
                del self.__lists[name][2][i]
                del self.__lists[name][4][i]
                break
        self.__display_list(name)

    def InList(self, name, prot_obj):
        if not name in self.__lists.keys():
            raise ValueError("No list %s exists in SimPanel." % name)
        return prot_obj in self.__lists[name][4]

    def RemoveList(self, name):
        if name in self.__lists.keys():
            self.ComponentTree.Delete(self.__lists[name][1])
            del self.__lists[name]
            if self.__displaying == name:
                self.Viewing.ClearAll()
                self.__displaying = ""
                if self.ComponentTree.GetItemParent(self.ComponentTree.GetSelection()) == self.ListTree:
                    self.__display_list(self.ComponentTree.GetItemText(self.ComponentTree.GetSelection()))

    def DoLayout(self):
        self.ComponentTree.SetMinSize((self.GetSize()[0] / 3, self.GetSize()[1]))
        self.Layout()

    def __update_ui(self):
        ic = self.__simulation.GetInternalComponents()
        for i in xrange(0, self.Viewing.GetItemCount()):
            with self.__analysis_lock:
                self.Viewing.SetItem(i, 1, '%.0f%%' % (self.__analysis[self.__lists[self.__displaying][4][i].speciesId]*100))
        for i in self.__tree_ext.keys():
            with self.__analysis_lock:
                self.ComponentTree.SetItemText( self.__tree_ext[i][0], '%s: %.1f%%' % (self.__tree_ext[i][1], self.__analysis[int(i)]) )

    cycle_n = 0
    def __thread_func(self):
        self.ActMonitor.Prepare()
        self.ActMonitor.Refresh()
        while True:
            with self.__running_lock:
                if not self.Running:
                    break
            if self.__do_restart:
                with self.__sim_lock:
                    self.__simulation.ResetSimulation()
                    self.__sim_steps.SetLabel("Frames 0-100")
                    self.__tb.Layout()
                    self.ActMonitor.Reset()
                    update_evt = UpdateMonitorEvent(steps = -1, activity_levels = None)
                    wx.PostEvent(self.ActMonitor, update_evt)
                    self.__do_restart = False
                    time.sleep(.01)
                    continue
            # Set view to next frame
            if self.__do_next:
                frm = self.ActMonitor.frame
                with self.__sim_lock:
                    max_frame = int(math.floor(self.__simulation.GetSteps() / 100))
                if frm != -1 and frm < max_frame:
                    self.__sim_steps.SetLabel("Frames %d-%d" % ((frm + 1)*100, (frm +2)*100))
                    self.__tb.Layout()
                self.ActMonitor.NextFrame()
                self.__do_next = False
            # Set view to previous frame
            if self.__do_prev:
                frm = self.ActMonitor.frame
                if frm == -1:
                    with self.__sim_lock:
                        max_frame = int(math.floor(self.__simulation.GetSteps() / 100))
                    self.__sim_steps.SetLabel("Frames %d-%d" % ((max_frame-1)*100, max_frame*100))
                    self.__tb.Layout()
                if frm != -1 and frm > 0:
                    self.__sim_steps.SetLabel("Frames %d-%d" % ((frm - 1)*100, frm*100))
                    self.__tb.Layout()
                self.ActMonitor.PreviousFrame()
                self.__do_prev = False
            cur_time = math.floor(time.time() * 1000)
            paused = False
            with self.__pause_lock:
                paused = self.paused
            if not self.paused:
                with self.__sim_lock:
                    self.__simulation.RunStep()
                    flval = int(math.floor(float(self.__simulation.GetSteps()) / 100)) # math.floor returns a float, convert to int here
                    if flval*100 == self.__simulation.GetSteps():
                        if self.ActMonitor.frame == -1:
                            self.__sim_steps.SetLabel("Frames %d-%d" % (flval*100, (flval+1)*100))
                            self.__tb.Layout()
                    state = self.__simulation.GetFullState()
                for i in state.keys():
                    i = int(i)
                    with self.__analysis_lock:
                        steps = self.__simulation.GetSteps()
                        if steps == 0:
                            steps = 1
                        self.__analysis[i] = float(self.__analysis[i]) + (float(float(state[i])-self.__analysis[i]) / float(steps))
                actm = {}
                with self.ActMonitor.ThreadLock:
                    gt = self.ActMonitor.GetTracking()
                for i in gt:
                    actm[i] = self.__analysis[i.speciesId]
                with self.ActMonitor.ThreadLock:
                    # To avoid messing with the buffer in a different thread
                    update_evt = UpdateMonitorEvent(steps = self.__simulation.GetSteps(), activity_levels=actm)
                    wx.PostEvent(self.ActMonitor, update_evt)
                self.cycle_n += 1
                if self.cycle_n == 5:
                    self.__update_ui()
                    self.cycle_n = 0
                else:
                    self.cycle_n += 1
            else:
                update_evt = UpdateMonitorEvent(steps = -1, activity_levels = None)
                wx.PostEvent(self.ActMonitor, update_evt)
            self.can_kill.set()
            new_time = math.floor(time.time() * 1000)
            while new_time - cur_time < self.__simulation_step:
                time.sleep(.005)
                new_time = math.floor(time.time() * 1000)
            self.can_kill.clear()
        self.Finished = True

    def Start(self):
        self.Running = True
        self.thread = threading.Thread(target=self.__thread_func)
        self.thread.daemon = True
        self.can_kill = threading.Event()
        self.thread.start()

    def Stop(self):
        if self.can_kill == None:
            raise ReferenceError("Call to Stop without call to Start.")
        if self.thread.isAlive():
            self.can_kill.wait()
            with self.__running_lock:
                self.Running = False
            while not self.Finished:
                time.sleep(.01)
        print("here")
