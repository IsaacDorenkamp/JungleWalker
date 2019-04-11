# wx extension library for JungleWalker - dialogs

import datetime
from dateutil.tz import tzlocal
import math
import pytz
import requests.exceptions
import threading
import time
import wx
import wx.lib.newevent
import wx.lib.scrolledpanel as wxscrolled

from jwaux import *
from modellib import *
import ccapi

# dragndrop api
import dragndrop

# My own word wrap calculator, because whoever wrote
# wx's is an idiot
global BIG_FONT
global WORDWRAP_TOLERANCE
global MODEL_DISPLAY_WIDTH
BIG_FONT = wx.Font(18, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
WORDWRAP_TOLERANCE = 5
MODEL_DISPLAY_WIDTH = 200
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
def BreakWordWrap_FirstLine(word, firstline_width, width, dc):
    if word == '':
        return ''
    pieces = word.split(' ')
    if dc.GetTextExtent(pieces[0])[0] > width - WORDWRAP_TOLERANCE:
        return '\n' + word
    out = ""
    for i in pieces:
        lines = out.split('\n')
        last_line = lines[len(lines)-1]
        if len(lines) == 1 and dc.GetTextExtent(last_line + i)[0] > firstline_width - WORDWRAP_TOLERANCE:
            out += "\n" + i + " "
        elif len(lines) > 1 and dc.GetTextExtent(last_line + i)[0] > width - WORDWRAP_TOLERANCE:
            out += "\n" + i + " "
        else:
            out += i + " "
    return out

class AuthDialog(wx.Dialog):
    def __init__(self, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        if not 'title' in kwargs.keys():
            self.SetTitle("Log In")

        self.__config_ui()
        self.Centre()

    def __config_ui(self):
        form = wx.Panel(self)
        ulbl = wx.StaticText(form, wx.ID_ANY, label="Username:")
        self.ufld = wx.TextCtrl(form, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        upwd = wx.StaticText(form, wx.ID_ANY, label="Password:")
        self.pfld = wx.TextCtrl(form, wx.ID_ANY, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)

        self.ufld.Bind(wx.EVT_TEXT_ENTER, self.__onsubmit)
        self.pfld.Bind(wx.EVT_TEXT_ENTER, self.__onsubmit)

        self.ufld.SetMinSize((200, 25))
        self.pfld.SetMinSize((200, 25))
        form_sizer = wx.FlexGridSizer(2, 2, (0,0))
        form_sizer.Add(ulbl, 1, wx.TOP | wx.BOTTOM | wx.LEFT | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, 6)
        form_sizer.Add(self.ufld, 5, wx.ALL | wx.EXPAND, 6)
        form_sizer.Add(upwd, 1, wx.TOP | wx.BOTTOM | wx.LEFT | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, 6)
        form_sizer.Add(self.pfld, 5, wx.ALL | wx.EXPAND, 6)
        form.SetSizer(form_sizer)

        okb  = wx.Button(self, wx.ID_OK)
        bsizer = wx.BoxSizer(wx.VERTICAL)

        bsizer.Add(form, 1, wx.EXPAND)
        bsizer.Add(okb, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        self.SetSizer(bsizer)

        self.Fit()

        self.Bind(wx.EVT_CLOSE, self.__onclose)

    def __onsubmit(self, evt):
        self.EndModal(wx.ID_OK)

    def __onclose(self, evt):
        self.EndModal(wx.ID_CANCEL)

    def GetUsername(self):
        return self.ufld.GetValue()

    def GetPassword(self):
        return self.pfld.GetValue()
        
class ModelSelectionDialog(wx.Dialog):
    MODEL_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S %Z'
    MODEL_DATE_DISPLAY_FORMAT = '%m/%d/%Y'
    
    def __init__(self, session, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)
        
        self.SetTitle("Loading Models")

        if not isinstance(session, ccapi.CCSession):
            raise TypeError("session must be an instance of ccapi.Session")

        self.__session = session

        self.__config_ui()
        self.Centre()

        self.selection = (-1, '', 0, 0, None)
        self.items = {}

        self.Bind(wx.EVT_CLOSE, self.__onclose)

        self.ready = threading.Event()

        t = threading.Thread(target=self.__load_models)
        t.start()

    def __onclose(self, evt):
        self.EndModal(wx.ID_CANCEL)

    def __setscroll(self):
        for i in self.__display.keys():
            self.__display[i].SetupScrolling()

    def __config_ui(self):
        self.__tabpane = wx.Notebook(self)
        self.__display = {}
        self.__create_category('research', 'Research')
        self.__create_category('learning', 'Education')
        self.__tabpane.Show(False)

        self.__loading = wx.Panel(self)
        lbl = wx.StaticText(self.__loading, label="...")
        lbl.SetFont(BIG_FONT)
        ls = wx.BoxSizer(wx.VERTICAL)
        ls.Add(lbl, 1, wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        self.__loading.SetSizer(ls)

        self.__display['research'].SetupScrolling()
        self.__display['learning'].SetupScrolling()

        ok = wx.Button(self, wx.ID_OK, label="OK")

        boxs = wx.BoxSizer(wx.VERTICAL)
        boxs.Add(self.__loading, 1, wx.EXPAND)
        boxs.Add(self.__tabpane, 1, wx.EXPAND)
        boxs.Add(ok, 0, wx.ALL | wx.ALIGN_CENTER, 7)

        self.SetSizer(boxs)

        self.SetMinSize((200, 0))
        self.Fit()

    def __set_selection(self, evt):
        e = evt.GetEventObject()
        o = self.items.get(e)
        if o == None:
            return
        for i in self.items.keys():
            if self.items[i] == self.selection:
                i.GetParent().SetBackgroundColour('white')
                break
        self.selection = o
        e.GetParent().SetBackgroundColour('green')
        self.Refresh()

    def __adjust_size(self):
        self.__loading.Show(False)
        self.__setscroll()
        for i in self.__display.keys():
            self.__display[i].Layout()
        self.__tabpane.Show()
        self.__tabpane.SetMinSize((self.__tabpane.GetCurrentPage().GetVirtualSize()[0] + 30, 500))
        self.Fit()
        self.Layout()
        self.Centre()
        self.__tabpane.Layout()
        self.__tabpane.GetCurrentPage().SetFocus()

    __models = {}
    def __create_category(self, name, label=None):
        if label == None:
            label = name
        self.__models[name] = 0
        self.__display[name] = wxscrolled.ScrolledPanel(self.__tabpane)
        self.__display[name].SetBackgroundColour('white')
        self.__display[name].SetMinSize((250, 500))
        gs = wx.FlexGridSizer(2)
        self.__display[name].SetSizer(gs)
        self.__tabpane.AddPage(self.__display[name], label)
        
    def __add_model(self, n, v, c, i, a, cd, upd_str, upd, mid, mh, mn, category='education'):
        if category == '':
            category = 'education'
        if self.__display.get(category) == None:
            raise Warning("Attempted to add model display to a category that doesn't exist: %s" % category)
        dc = wx.ClientDC(self)
        b = BreakWordWrap
        sp = wx.Panel(self.__display[category], style=wx.SIMPLE_BORDER)
        ns = b("%s (Version %s)\n" % (n, v), MODEL_DISPLAY_WIDTH, dc)
        cs = b("Components: %s" % c, MODEL_DISPLAY_WIDTH, dc)
        ins = b("Interactions: %s" % i, MODEL_DISPLAY_WIDTH, dc)
        if a == None:
            au = ""
        else:
            au = b("\nAuthor: %s" % a, MODEL_DISPLAY_WIDTH, dc)
        cds = b("Created: %s" % cd, MODEL_DISPLAY_WIDTH, dc)
        _up = b("Updated: %s" % upd_str, MODEL_DISPLAY_WIDTH, dc)
        st = wx.StaticText(sp, label="%s\n%s\n%s%s\n%s\n%s" % (ns, cs, ins, au, cds, _up))
        boxs = wx.BoxSizer(wx.VERTICAL)
        boxs.Add(st, 1, wx.ALL | wx.EXPAND, border=10)
        self.__models[category] += 1
        sp.SetSizer(boxs)
        self.items[st] = (mid, mh, int(v), mn, upd)
        st.Bind(wx.EVT_LEFT_DOWN , self.__set_selection)
        st.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.__display[category].GetSizer().Add(sp, 1, wx.ALL | wx.EXPAND, border = 5)
        if self.__models[category] == 1:
            self.__display[category].GetSizer().AddGrowableCol(0)
        elif self.__models[category] == 2:
            self.__display[category].GetSizer().AddGrowableCol(1)

    def __load_models(self):
        try:
            mods = self.__session.GetAvailableModels()
        except requests.exceptions.ConnectionError:
            wx.CallAfter(self.Destroy)
            wx.CallAfter( wx.MessageBox, 'Could not connect to the internet. No models could be fetched.', 'Network Error', wx.ICON_ERROR | wx.OK )
            return
        if isinstance(self.__session, ccapi.AuthSession):
            wx.CallAfter(self.__create_category, 'personal', 'My Models')
            wx.CallAfter(self.__create_category, 'shared', 'Shared with Me')
        for i in mods:
            m = i['model']
            name = m['name']
            version = m['currentVersion']
            components = m['components']
            interactions = m['interactions']
            author = m['author']
            
            creationDate = pytz.utc.localize( datetime.datetime.strptime( m['creationDate'], self.MODEL_DATE_FORMAT ) )
            creationDate = creationDate.astimezone( tzlocal() ).strftime(self.MODEL_DATE_DISPLAY_FORMAT)

            logicUpdated = datetime.datetime.strptime(m['biologicUpdateDate'], self.MODEL_DATE_FORMAT)
            kbUpdated    = datetime.datetime.strptime(m['knowledgeBaseUpdateDate'], self.MODEL_DATE_FORMAT)
            updatedDate = pytz.utc.localize(max(logicUpdated, kbUpdated))
            updatedDate = updatedDate.astimezone( tzlocal() )
            uds = updatedDate.strftime(self.MODEL_DATE_DISPLAY_FORMAT)
            
            if m['published']:
                # Add to list of public models
                wx.CallAfter( self.__add_model, name, version, components, interactions, author, creationDate, uds, updatedDate, m['id'], i['hash'], m['name'],
                              m.get('type', '') )
            else:
                if i['modelPermissions']['edit'] and not all(i['modelPermissions'].values()):
                    wx.CallAfter( self.__add_model, name, version, components, interactions, author, creationDate, uds, updatedDate, m['id'], i['hash'], m['name'],
                                  'shared' )
                elif all(i['modelPermissions'].values()):
                    wx.CallAfter( self.__add_model, name, version, components, interactions, author, creationDate, uds, updatedDate, m['id'], i['hash'], m['name'],
                                  'personal' )
        wx.CallAfter(self.SetTitle, 'Select a Model')
        wx.CallAfter(self.__adjust_size)

    def GetSelectedModelID(self):
        return self.selection

class SelectListDialog(wx.Dialog):
    def __init__(self, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        self.__lb = wx.ListBox(self)
        ok = wx.Button(self, wx.ID_OK, label="OK")

        boxer = wx.BoxSizer(wx.VERTICAL)
        boxer.Add(self.__lb, 0, wx.EXPAND)
        boxer.Add(ok, 0, wx.ALL | wx.ALIGN_CENTER, border=8)

        self.SetMinSize((250,125))

        self.SetSizer(boxer)

        self.Fit()

        self.Centre()
    def SetLists(self, lists):
        for i in lists:
            self.__lb.Append(i)
    def GetList(self):
        if self.__lb.GetSelection() == -1:
            return ''
        return self.__lb.GetString(self.__lb.GetSelection())

class TrackListDialog(wx.Dialog):
    def __init__(self, activity_monitor, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        self.__activity_monitor = activity_monitor

        self.list_box = wx.ListBox(self)

        items = self.__activity_monitor.GetTracking()
        items.sort(key=lambda x: x.name.lower)
        for i in items:
            self.list_box.Append(i)

        self.remove = wx.Button(self, wx.ID_DELETE)
        self.ok = wx.Button(self, wx.ID_OK)

        boxer = wx.BoxSizer(wx.VERTICAL)

        boxer.Add(self.list_box, 0, wx.EXPAND)
        boxer.Add(self.remove, 0, wx.EXPAND)
        boxer.Add(self.ok, 0, wx.ALL | wx.ALIGN_CENTER, border=15)

        self.SetSizer(boxer)

        self.SetMinSize( (250, 125) )
        self.Fit()

        self.Bind( wx.EVT_BUTTON, self.__remove_item, self.remove )

        self.Centre()

    def __remove_item(self, evt):
        s = self.list_box.GetString(self.list_box.GetSelection())
        self.__activity_monitor.UnTrack(s)
        self.list_box.Delete(self.list_box.GetSelection())

# LogicEditor Auxiliary Classes
class LabelBox(wx.Panel):
    def __init__(self, text, parent, config_label=True):
        wx.Panel.__init__(self, parent)

        self.__top_box = wx.Panel(self)
        self.__top_box.SetBackgroundColour('#d8d8d8')
        self.__st = wx.StaticText(self.__top_box, label=text)

        tbs = wx.BoxSizer()
        self.__top_box.SetSizer(tbs)

        self.__rsize = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.__rsize)
        self.__rsize.Add(self.__top_box, 1, wx.EXPAND)

        self.__label_config = False
        if config_label:
            self.ConfigLabel()
        
    def ConfigLabel(self):
        if self.__label_config:
            raise RuntimeError("Label already configured!")
        self.__top_box.GetSizer().Add(self.__st, 0, wx.ALL, 5)
        self.__label_config = True

    def GetTopBox(self):
        return self.__top_box

# Regulator wx lib
RegulatorAddedEvent, EVT_REGULATOR_ADDED = wx.lib.newevent.NewCommandEvent()
RegulatorRemovedEvent, EVT_REGULATOR_REMOVED = wx.lib.newevent.NewCommandEvent()
RelayoutEvent, EVT_RELAYOUT = wx.lib.newevent.NewEvent()
jwID_NO_DOMINANCES = wx.NewId()

class RegulatorBox(LabelBox):
    LABEL_PADDING = 5
    
    def __init__(self, name, ispositive, parent, ccnode, regId, model, dragndrop):
        LabelBox.__init__(self, name, parent, False)

        self.__ccnode = ccnode
        self.__regId = regId
        self.__ispos  = ispositive

        try:
            self.CLOSE_X = wx.Image('./img/close.png', type=wx.BITMAP_TYPE_PNG).ConvertToBitmap()
            self.CLOSE_X.SetMaskColour('#f8f8f8')
        except Exception as e:
            self.CLOSE_X = wx.Bitmap(16, 16)

        # RESOLVED: I will not attempt to create an "image bucket" system, the difference
        # in efficiency is negligible and it is not worth creating an entire new system
        # to reduce an unnoticeable inefficiency.
        if ispositive:
            im = wx.Image('./img/positive.png', 'image/png').ConvertToBitmap()
        else:
            im = wx.Image('./img/negative.png', 'image/png').ConvertToBitmap()

        plusi = wx.Image('./img/add.png', 'image/png')
        for y in xrange(0, plusi.GetHeight()):
            for x in xrange(0, plusi.GetWidth()):
                plusi.SetRGB( x, y, 200, 200, 200 )
                plusi.SetAlpha(x, y, 255 - plusi.GetAlpha(x, y))
        plus = plusi.ConvertToBitmap()

        imb = wx.StaticBitmap(self.GetTopBox(), wx.ID_ANY, im)

        for i in self.GetTopBox().GetChildren():
            if isinstance(i, wx.StaticText):
                self.GetTopBox().SetForegroundColour('#747474')

        close_x = wx.BitmapButton( self.GetTopBox(), wx.ID_ANY, self.CLOSE_X, style=wx.NO_BORDER )
        close_x.SetBackgroundColour( self.GetTopBox().GetBackgroundColour() )
        close_x.SetCursor( wx.Cursor(wx.CURSOR_HAND) )
        close_x.Bind(wx.EVT_BUTTON, self.RemoveRegulator)

        self.GetTopBox().GetSizer().Add(imb, 0, wx.TOP | wx.LEFT | wx.BOTTOM, 5)
        self.ConfigLabel()
        self.GetTopBox().GetSizer().AddStretchSpacer()
        # Configure dominances is this regulator is negative
        if not ispositive:
            self.__dom = wx.StaticText(self.GetTopBox(), label="Dominance")
            self.GetTopBox().GetSizer().Add(self.__dom, 0, wx.ALL, 5)

            self.__dom_menu = wx.Menu()

            self.__doms = {}
            self.__dom_items = {}
            self.__dom_menu_items = {}

            self.__dom.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            self.__dom.Bind( wx.EVT_LEFT_DOWN, self.__startclick )
            self.__dom.Bind( wx.EVT_LEAVE_WINDOW, self.__abortclick )
            self.__dom.Bind( wx.EVT_LEFT_UP, self.__checkclick )
            self.click = False

            self.Bind(EVT_REGULATOR_REMOVED, self.__neg_adjust_dom)
        else:
            self.__dom = None
            self.__dom_menu = None
            self.__doms = None
            self.__dom_items = None
            self.__dom_menu_items = None
        self.GetTopBox().GetSizer().Add(close_x, 0, wx.ALL, 5)

        cbox = wx.Panel(self)
        cbox.SetBackgroundColour('white')
        cboxs = wx.BoxSizer()
        clbl = wx.StaticText(cbox, label="Conditions")
        self.__cimg = wx.BitmapButton(cbox, wx.ID_ANY, plus, style=wx.NO_BORDER)
        self.__cimg.SetBackgroundColour(cbox.GetBackgroundColour())
        self.__cimg.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        cboxs.Add(clbl)
        cboxs.Add(self.__cimg, 0, wx.LEFT, 5)
        cbox.SetSizer(cboxs)

        self.GetSizer().Add( cbox, 0, wx.ALL, 5 )

        # Prepare handler to add conditions
        def _add_cond(evt):
            self.AddEmptyCondition(model, dragndrop)
            cur = parent
            while cur.GetParent() != None:
                cur = cur.GetParent()
            cur.relayout(None)
            dragndrop.Reconfigure()
            
        self.__cimg.Bind(wx.EVT_BUTTON, _add_cond)

        self.__conditions = {}
        self.__subconds = {}

        self.__relation_configured = {} # This is used to keep track of which conditions have configured a "relation" label to change between Independent and
                                        # Co-operative relations between species in the condition.
        self.__sc_relation_configured = {}

        self.SetWindowStyle(wx.SIMPLE_BORDER)

        self.Bind(EVT_REGULATOR_ADDED, self.__on_new_posreg)

    def __neg_adjust_dom(self, evt):
        if not self.__ispos and evt.positive:
            self._remove_dom(evt.reg_id)

    def IsPositive(self):
        return self.__ispos

    def __on_new_posreg(self, evt):
        self._add_dom(evt.reg_id, evt.reg_name)

    def __startclick(self, evt):
        self.click = True

    def __abortclick(self, evt):
        self.click = False

    def __checkclick(self, evt):
        if self.click:
            self.click = False
            self.OnClick(evt)

    def OnClick(self, evt):
        if self.__dom_menu != None:
            self.__dom.PopupMenu(self.__dom_menu, (0, self.__dom.GetSize()[1]))

    def RemoveRegulator(self, evt=None):
        p = self.GetParent()
        p.RemoveChild(self)
        p.GetSizer().Hide(self.GetSizer())
        p.GetSizer().Remove(self.GetSizer())
        self.Destroy()

        master = p
        while master.GetParent() != None:
            master = master.GetParent()
        rel_evt = RelayoutEvent()
        wx.PostEvent(master, rel_evt)

        rmv_evt = RegulatorRemovedEvent(wx.wxEVT_NULL, positive=self.__ispos, reg_id=self.__regId)
        wx.PostEvent(p, rmv_evt)
        
        p.Layout()
        if isinstance(p, wxscrolled.ScrolledPanel):
            p.SetupScrolling(scroll_x = False)
        self.__ccnode.RemoveReg(self.__regId)

    # Dominance Functions
    def _add_dom(self, posreg, name, default_value=True):
        assert not self.__ispos, "Cannot add dominance to a positive regulator!"
        nodom_item = self.__dom_menu.FindItemById(jwID_NO_DOMINANCES)
        if nodom_item != None:
            self.__dom_menu.Delete(nodom_item)
        item = self.__dom_menu.AppendCheckItem(wx.ID_ANY, name)
        self.__dom_items[posreg] = default_value
        self.__ccnode.SetDominance(posreg, self.__regId, default_value)
        if default_value:
            item.Check()
        self.__dom_menu_items[posreg] = item

        def adjust_dom(evt):
            self.__dom_items[posreg] = item.IsChecked()
            self.__ccnode.SetDominance(posreg, self.__regId, item.IsChecked())

            if self.__ccnode.Dominances(self.__regId) == 0:
                f = self.__dom.GetFont()
                f.SetWeight(wx.FONTWEIGHT_LIGHT)
                self.__dom.SetFont(f)
            else:
                f = self.__dom.GetFont()
                f.SetWeight(wx.FONTWEIGHT_BOLD)
                self.__dom.SetFont(f)

        if self.__ccnode.Dominances(self.__regId) > 0 and self.__dom.GetFont().GetWeight() != wx.FONTWEIGHT_BOLD:
                f = self.__dom.GetFont()
                f.SetWeight(wx.FONTWEIGHT_BOLD)
                self.__dom.SetFont(f)

        self.__dom_menu.Bind( wx.EVT_MENU, adjust_dom, item )

    def _no_doms(self):
        # to call only if there are no pos regs
        assert not self.__ispos, "Cannot configure dominances on a positive regulator."
        f = self.__dom.GetFont()
        f.SetWeight(wx.FONTWEIGHT_LIGHT)
        self.__dom.SetFont(f)
        self.__dom_menu.Append(jwID_NO_DOMINANCES, "No Positive Regulators")

    def _remove_dom(self, posreg):
        # to call when a positive regulator is removed (_add_dom will be called upon the addition of a new positive regulator)
        assert not self.__ispos, "Cannot removed dominance from a positive regulator!"
        if posreg in self.__dom_items.keys():
            del self.__dom_items[posreg]
            self.__dom_menu.Delete(self.__dom_menu_items[posreg])
            self.__ccnode.RemoveAllDominances(posreg)
            if len(self.__ccnode.GetPosRegs()) == 0:
                self._no_doms()
        
    def SetDominance(self, posreg, domval=True):
        assert not self.__ispos, "Cannot set dominance of a positive regulator!"
        self.__dom_items[posreg] = domval
        self.__ccnode.SetDominance(posreg, self.__regId, domval)

    def AddEmptyCondition(self, model, dragndrop = None):
        self.AddCondition([], 'or', False, 'ON', IDManager.NextConditionId(), model, dragndrop)
        
    def AddCondition(self, speclist, relation, negate, state, condId, model, dragndrop=None):
        _cbox = wx.Panel(self, style=wx.SIMPLE_BORDER)
        _cbox.SetBackgroundColour('#f0f0f0')

        cbox = wx.Panel(_cbox)
        _cbox.SetSizer(wx.BoxSizer(wx.VERTICAL))
        
        if negate:
            tp = "Unless "
        else:
            tp = "If/When "
            
        if state == "ON":
            st = "Active"
        else:
            st = "Inactive"

        is_red = (negate ^ (state=="OFF"))

        cbar = wx.Panel(_cbox)
        cbar_size = wx.BoxSizer()
        cbar.SetSizer(cbar_size)
        
        cond_lbl = wx.StaticText(cbar, label="Condition")
        f = cond_lbl.GetFont()
        f.SetWeight(wx.FONTWEIGHT_BOLD)
        cond_lbl.SetFont(f)
        cond_lbl.SetForegroundColour('#d0d0d0')

        close_x = wx.BitmapButton( cbar, wx.ID_ANY, self.CLOSE_X, style=wx.NO_BORDER )
        close_x.SetCursor( wx.Cursor(wx.CURSOR_HAND) )
        close_x.Bind(wx.EVT_BUTTON, lambda evt: self.RemoveCondition(condId))

        cbar_size.Add( cond_lbl, 0 )
        cbar_size.AddStretchSpacer()
        cbar_size.Add( close_x, 0 )
            
        cond_type = wx.StaticText(cbox, label=tp)
        if len(speclist) > 0:
            ctxt = (' ' + relation + ' ').join(speclist)
            c_fg = '#747474'
        else:
            ctxt = '(Drop Regulators Here)'
            c_fg = '#cdcdcd'
        cond_list = wx.StaticText(cbox, label=ctxt)
        cond_list.SetCursor( wx.Cursor(wx.CURSOR_ARROW) )
        cond_list.SetBackgroundColour( cbox.GetBackgroundColour() )
        cond_list.SetMinSize( (wx.ClientDC(cond_list).GetTextExtent(ctxt)[0] + 2, 0) )
        state_lbl = wx.StaticText(cbox, label="is %s" % st)
        state_lbl.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        cbox.FitInside()

        def update_ui(relation_lbl):
            state = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_STATE_IDX)
            if state == "ON":
                stxt = "is Active"
            else:
                stxt = "is Inactive"
            state_lbl.SetLabelText(stxt)
            state_lbl.SetMinSize((wx.ClientDC(state_lbl).GetTextExtent(stxt)[0], state_lbl.GetSize()[1]))

            clause = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_CSTR_IDX)
            if clause == "":
                ctxt = "If/When "
            else:
                ctxt = "Unless "
            cond_type.SetLabelText(ctxt)
            cond_type.SetMinSize((wx.ClientDC(cond_type).GetTextExtent(ctxt)[0], cond_type.GetSize()[1]))

            nspeclist = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECLIST_IDX)
            nspecrel  = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECREL_IDX)

            spectxt = (' ' + nspecrel + ' ').join([model['speciesMap'][unicode(i)]['name'] for i in nspeclist])
            cond_list.SetLabelText(spectxt)
            cond_list.Wrap(cbox.GetSize()[0] - 10)
            cond_list.SetMinSize( (wx.ClientDC(cond_list).GetTextExtent(spectxt)[0] + RegulatorBox.LABEL_PADDING, cond_list.GetSize()[1]) )
            cond_list.Refresh()
            
            # reset all the colors
            is_red = (self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_STATE_IDX) == "OFF") \
                        ^ (self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_CSTR_IDX) == "not ")

            if is_red:
                color = wx.Colour('#e84c3d')
            else:
                color = wx.Colour('#27ae61')

            cond_type.SetForegroundColour(color)
            state_lbl.SetForegroundColour(color)

            if relation_lbl != None:
                nrel = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECREL_IDX)
                if nrel == 'or':
                    rtxt = "(Independent)"
                else:
                    rtxt = "(Co-operative)"
                relation_lbl.SetLabelText(rtxt)
            else:
                if len(nspeclist) > 1:
                    if relation == 'or':
                        txt = "(Independent)"
                    else:
                        txt = "(Co-operative)"
                    relation_lbl = wx.TextCtrl(cbox, value=txt, style=wx.TE_READONLY | wx.NO_BORDER )
                    relation_lbl.SetBackgroundColour( cbox.GetBackgroundColour() )
                    relation_lbl.SetCursor(wx.Cursor(wx.CURSOR_HAND))
                    relation_lbl.SetForegroundColour('#747474')

                    self.__relation_configured[condId] = relation_lbl
                    
                    def toggle(evt):
                        rel = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECREL_IDX)
                        if rel == 'or':
                            newrel = 'and'
                        else:
                            newrel = 'or'
                        self.__ccnode.SetConditionProperty(condId, CCNode.CONDITION_SPECREL_IDX, newrel)
                        update_ui(self.__relation_configured.get(condId))
                    cboxs.Add(relation_lbl, wx.EXPAND, 0)
                    relation_lbl.Bind(wx.EVT_LEFT_DOWN, toggle)

            sz = self.GetSize()
            self.SetMaxSize((sz[0], sz[0]+500))
            cbox.Fit()
            _cbox.Fit()
            self.Layout()
            self.Refresh() # avoid ugly graphics artifacts

            # we're gonna get the top level window
            cur = self
            while cur.GetParent() != None:
                cur = cur.GetParent()
            revt = RelayoutEvent()
            wx.PostEvent(cur, revt) 

        def toggle_st(evt):
            state = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_STATE_IDX)
            if state == "ON":
                newstate = "OFF"
            else:
                newstate = "ON"
            self.__ccnode.SetConditionProperty(condId, CCNode.CONDITION_STATE_IDX, newstate)

            update_ui(self.__relation_configured.get(condId))
            
        state_lbl.Bind(wx.EVT_LEFT_DOWN, toggle_st)

        def toggle_clause(evt):
            clause = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_CSTR_IDX)
            if clause == "not ":
                newclause = ""
            else:
                newclause = "not "
            self.__ccnode.SetConditionProperty(condId, CCNode.CONDITION_CSTR_IDX, newclause)

            update_ui(self.__relation_configured.get(condId))

        cond_type.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        cond_type.Bind(wx.EVT_LEFT_DOWN, toggle_clause)

        if is_red:
            color = wx.Colour('#e84c3d')
        else:
            color = wx.Colour('#27ae61')

        if len(speclist) > 1:
            if relation == 'or':
                txt = "(Independent)"
            else:
                txt = "(Co-operative)"
            relation_lbl = wx.TextCtrl(cbox, value=txt, style=wx.TE_READONLY | wx.NO_BORDER )
            relation_lbl.SetBackgroundColour( cbox.GetBackgroundColour() )
            relation_lbl.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            def toggle(evt):
                rel = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECREL_IDX)
                if rel == 'or':
                    newrel = 'and'
                else:
                    newrel = 'or'
                self.__ccnode.SetConditionProperty(condId, CCNode.CONDITION_SPECREL_IDX, newrel)
                update_ui(self.__relation_configured.get(condId))
            
            relation_lbl.Bind(wx.EVT_LEFT_DOWN, toggle)

            self.__relation_configured[condId] = relation_lbl
        else:
            relation_lbl = None

        cond_type.SetForegroundColour(color)
        cond_list.SetForegroundColour(c_fg)
        state_lbl.SetForegroundColour(color)

        # loading the plus image, I am very aware that I could make this more efficient by storing the
        # image in some sort of "image bucket" the first time I load it, but I'm simply trying to have
        # an application that works well, thank you very much.
        plusi = wx.Image('./img/add.png', 'image/png')
        for y in xrange(0, plusi.GetHeight()):
            for x in xrange(0, plusi.GetWidth()):
                plusi.SetRGB( x, y, 200, 200, 200 )
                plusi.SetAlpha(x, y, 255 - plusi.GetAlpha(x, y))
        plus = plusi.ConvertToBitmap()

        scbox = wx.Panel(_cbox)
        sclbl = wx.StaticText(scbox, label="SubConditions")
        sclbl.SetForegroundColour('#747474')
        
        scimg = wx.BitmapButton(scbox, wx.ID_ANY, plus, style=wx.NO_BORDER)
        scimg.SetBackgroundColour(scbox.GetBackgroundColour())
        scimg.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        scboxs = wx.BoxSizer()
        scboxs.Add(sclbl)
        scboxs.Add(scimg, 0, wx.LEFT, 5)
        scbox.SetSizer(scboxs)

        # Prepare handler to add conditions
        def _add_subcond(evt):
            self.AddEmptySubCondition(condId, model, dragndrop)
            cur = _cbox
            while cur.GetParent() != None:
                cur = cur.GetParent()
            cur.relayout(None)
            dragndrop.Reconfigure()
            
        scimg.Bind(wx.EVT_BUTTON, _add_subcond)

        cboxs = wx.WrapSizer()
        cboxs.Add(cond_type, 0, wx.EXPAND)
        cboxs.Add(cond_list, 0, wx.EXPAND)
        cboxs.Add(state_lbl, 0, wx.EXPAND)
        if relation_lbl != None:
            relation_lbl.SetForegroundColour('#747474')
            cboxs.Add(relation_lbl, 0, wx.EXPAND)
        
        cbox.SetSizer(cboxs)

        _cbox.GetSizer().Add(cbar, 0, wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND, 6)
        _cbox.GetSizer().Add(cbox, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        _cbox.GetSizer().Add(scbox, 0, wx.ALL, 6)

        self.GetSizer().Add(_cbox, 0, wx.LEFT | wx.BOTTOM | wx.RIGHT | wx.EXPAND, 6)

        self.__conditions[condId] = _cbox

        # config dragndrop stuff
        if dragndrop != None:
            def drophandler(data):
                _speclist = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECLIST_IDX)
                if _speclist == None:
                    self.__ccnode.AddCondition(self.__regId, condId, 'or', 'or', 'ON', 'IF_WHEN', [], [])
                    _speclist = self.__ccnode.GetConditionProperty(condId, CCNode.CONDITION_SPECLIST_IDX)
                    cond_list.SetForegroundColour('#747474')
                if not data in _speclist:
                    _speclist.append(data)
                self.__ccnode.SetConditionProperty(condId, CCNode.CONDITION_SPECLIST_IDX, _speclist)
                
                update_ui(self.__relation_configured.get(condId))
                
            dragndrop.MakeDropTarget(_cbox, drophandler)

    def RemoveCondition(self, condId):
        # Remove Graphical Condition Box
        condition_box = self.__conditions.get(condId)
        if condition_box == None:
            return
        p = condition_box.GetParent()
        p.RemoveChild(condition_box)
        p.GetSizer().Hide(condition_box.GetSizer())
        p.GetSizer().Remove(condition_box.GetSizer())
        condition_box.Destroy()
        p.GetParent().Layout()

        cur = p
        while cur.GetParent() != None:
            cur = cur.GetParent()
        evt = RelayoutEvent()
        wx.PostEvent(cur, evt)
        # Remove Condition in the CCNode
        self.__ccnode.RemoveCondition(condId)

    def AddEmptySubCondition(self, condId, model, dragndrop=None):
        self.AddSubCondition([], 'or', False, 'ON', condId, IDManager.NextSubConditionID(), model, dragndrop)

    def AddSubCondition(self, speclist, relation, negate, state, condId, subCondId, model, dragndrop=None):
        #def AddCondition(self, speclist, relation, negate, state, condId, model, dragndrop=None):
        _pcbox = self.__conditions.get(condId)
        if _pcbox == None:
            return
        _cbox = wx.Panel(_pcbox, style=wx.SIMPLE_BORDER)
        _cbox.SetBackgroundColour('#f0f0f0')

        cbox = wx.Panel(_cbox)
        _cbox.SetSizer(wx.BoxSizer(wx.VERTICAL))
        
        if negate:
            tp = "Unless "
        else:
            tp = "If/When "
            
        if state == "ON":
            st = "Active"
        else:
            st = "Inactive"

        is_red = (negate ^ (state=="OFF"))

        cbar = wx.Panel(_cbox)
        cbar_size = wx.BoxSizer()
        cbar.SetSizer(cbar_size)
        
        cond_lbl = wx.StaticText(cbar, label="SubCondition")
        f = cond_lbl.GetFont()
        f.SetWeight(wx.FONTWEIGHT_BOLD)
        cond_lbl.SetFont(f)
        cond_lbl.SetForegroundColour('#d0d0d0')

        close_x = wx.BitmapButton( cbar, wx.ID_ANY, self.CLOSE_X, style=wx.NO_BORDER )
        close_x.SetCursor( wx.Cursor(wx.CURSOR_HAND) )
        close_x.Bind(wx.EVT_BUTTON, lambda evt: self.RemoveSubCondition(subCondId))

        cbar_size.Add( cond_lbl, 0 )
        cbar_size.AddStretchSpacer()
        cbar_size.Add( close_x, 0 )
            
        cond_type = wx.StaticText(cbox, label=tp)
        if len(speclist) > 0:
            ctxt = (' ' + relation + ' ').join(speclist)
            c_fg = '#747474'
        else:
            dc = wx.ClientDC(cbox)
            ctxt = '(drop nodes here)'
            c_fg = '#cdcdcd'
        cond_list = wx.StaticText(cbox, label=ctxt)
        cond_list.SetCursor( wx.Cursor(wx.CURSOR_ARROW) )
        cond_list.SetBackgroundColour( cbox.GetBackgroundColour() )
        cond_list.SetMinSize( (wx.ClientDC(cond_list).GetTextExtent(ctxt)[0] + 2, 0) )
        state_lbl = wx.StaticText(cbox, label="is %s" % st)
        state_lbl.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        def update_ui(relation_lbl):
            if self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_ID_IDX) == None:
                return
            state = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_STATE_IDX)
            if state == "ON":
                stxt = "is Active"
            else:
                stxt = "is Inactive"
            state_lbl.SetLabelText(stxt)
            state_lbl.SetMinSize((wx.ClientDC(state_lbl).GetTextExtent(stxt)[0], state_lbl.GetSize()[1]))

            clause = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_CSTR_IDX)
            if clause == "":
                ctxt = "If/When "
            else:
                ctxt = "Unless "
            cond_type.SetLabelText(ctxt)
            cond_type.SetMinSize((wx.ClientDC(cond_type).GetTextExtent(ctxt)[0], cond_type.GetSize()[1]))

            nspeclist = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECLIST_IDX)
            nspecrel  = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECREL_IDX)

            spectxt = (' ' + nspecrel + ' ').join([model['speciesMap'][unicode(i)]['name'] for i in nspeclist])
            cond_list.SetLabelText(spectxt)
            cond_list.Wrap(cbox.GetSize()[0] - 10)
            cond_list.SetMinSize( (wx.ClientDC(cond_list).GetTextExtent(spectxt)[0] + RegulatorBox.LABEL_PADDING, cond_list.GetSize()[1]) )
            cond_list.Refresh()
            
            # reset all the colors
            is_red = (self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_STATE_IDX) == "OFF") \
                        ^ (self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_CSTR_IDX) == "not ")

            if is_red:
                color = wx.Colour('#e84c3d')
            else:
                color = wx.Colour('#27ae61')

            cond_type.SetForegroundColour(color)
            state_lbl.SetForegroundColour(color)

            if relation_lbl != None:
                nrel = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECREL_IDX)
                if nrel == 'or':
                    rtxt = "(Independent)"
                else:
                    rtxt = "(Co-operative)"
                relation_lbl.SetLabelText(rtxt)
            else:
                if len(nspeclist) > 1:
                    if relation == 'or':
                        txt = "(Independent)"
                    else:
                        txt = "(Co-operative)"
                    relation_lbl = wx.TextCtrl(cbox, value=txt, style=wx.TE_READONLY | wx.NO_BORDER )
                    relation_lbl.SetBackgroundColour( cbox.GetBackgroundColour() )
                    relation_lbl.SetCursor(wx.Cursor(wx.CURSOR_HAND))
                    relation_lbl.SetForegroundColour('#747474')

                    self.__sc_relation_configured[subCondId] = relation_lbl
                    
                    def toggle(evt):
                        rel = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECREL_IDX)
                        if rel == 'or':
                            newrel = 'and'
                        else:
                            newrel = 'or'
                        self.__ccnode.SetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECREL_IDX, newrel)
                        update_ui(self.__sc_relation_configured.get(subCondId))
                    cboxs.Add(relation_lbl, wx.EXPAND, 0)
                    relation_lbl.Bind(wx.EVT_LEFT_DOWN, toggle)

            sz = self.GetSize()
            self.SetMaxSize((sz[0], sz[0]+500))
            cbox.Fit()
            _cbox.Fit()
            self.Layout()
            self.Refresh() # avoid ugly graphics artifacts

            # we're gonna get the top level window
            cur = self
            while cur.GetParent() != None:
                cur = cur.GetParent()
            revt = RelayoutEvent()
            wx.PostEvent(cur, revt) 

        def toggle_st(evt):
            state = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_STATE_IDX)
            if state == "ON":
                newstate = "OFF"
            else:
                newstate = "ON"
            self.__ccnode.SetSubConditionProperty(subCondId, CCNode.SUBCONDITION_STATE_IDX, newstate)

            update_ui(self.__sc_relation_configured.get(subCondId))
            
        state_lbl.Bind(wx.EVT_LEFT_DOWN, toggle_st)

        def toggle_clause(evt):
            clause = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_CSTR_IDX)
            if clause == "not ":
                newclause = ""
            else:
                newclause = "not "
            self.__ccnode.SetSubConditionProperty(subCondId, CCNode.SUBCONDITION_CSTR_IDX, newclause)

            update_ui(self.__sc_relation_configured.get(subCondId))

        cond_type.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        cond_type.Bind(wx.EVT_LEFT_DOWN, toggle_clause)

        if is_red:
            color = wx.Colour('#e84c3d')
        else:
            color = wx.Colour('#27ae61')

        if len(speclist) > 1:
            if relation == 'or':
                txt = "(Independent)"
            else:
                txt = "(Co-operative)"
            relation_lbl = wx.TextCtrl(cbox, value=txt, style=wx.TE_READONLY | wx.NO_BORDER )
            relation_lbl.SetBackgroundColour( cbox.GetBackgroundColour() )
            relation_lbl.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            def toggle(evt):
                rel = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECREL_IDX)
                if rel == 'or':
                    newrel = 'and'
                else:
                    newrel = 'or'
                self.__ccnode.SetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECREL_IDX, newrel)
                update_ui(self.__sc_relation_configured.get(subCondId))
            
            relation_lbl.Bind(wx.EVT_LEFT_DOWN, toggle)

            self.__sc_relation_configured[subCondId] = relation_lbl
        else:
            relation_lbl = None

        cond_type.SetForegroundColour(color)
        cond_list.SetForegroundColour(c_fg)
        state_lbl.SetForegroundColour(color)

        cboxs = wx.WrapSizer()
        cboxs.Add(cond_type, 0, wx.EXPAND)
        cboxs.Add(cond_list, 0, wx.EXPAND)
        cboxs.Add(state_lbl, 0, wx.EXPAND)
        if relation_lbl != None:
            relation_lbl.SetForegroundColour('#747474')
            cboxs.Add(relation_lbl, 0, wx.EXPAND)
        
        cbox.SetSizer(cboxs)

        _cbox.GetSizer().Add(cbar, 0, wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND, 6)
        _cbox.GetSizer().Add(cbox, 0, wx.ALL | wx.EXPAND, 6)

        _pcbox.GetSizer().Add(_cbox, 0, wx.LEFT | wx.BOTTOM | wx.RIGHT | wx.EXPAND, 6)

        self.__subconds[subCondId] = _cbox

        _cbox.Fit()

        # config dragndrop stuff
        if dragndrop != None:
            def drophandler(data):
                _speclist = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECLIST_IDX)
                if _speclist == None:
                    self.__ccnode.AddSubCondition(condId, subCondId, 'or', 'ON', 'IF_WHEN', [])
                    _speclist = self.__ccnode.GetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECLIST_IDX)
                    cond_list.SetForegroundColour('#747474')
                if not data in _speclist:
                    _speclist.append(data)
                self.__ccnode.SetSubConditionProperty(subCondId, CCNode.SUBCONDITION_SPECLIST_IDX, _speclist)
                
                update_ui(self.__sc_relation_configured.get(subCondId))
                
            dragndrop.MakeDropTarget(_cbox, drophandler)

    def RemoveSubCondition(self, subCondId):
        # Remove Graphical SubCondition Box
        condition_box = self.__subconds.get(subCondId)
        if condition_box == None:
            return
        p = condition_box.GetParent()
        p.RemoveChild(condition_box)
        p.GetSizer().Hide(condition_box.GetSizer())
        p.GetSizer().Remove(condition_box.GetSizer())
        condition_box.Destroy()
        p.GetParent().Layout()
        p.GetParent().GetParent().Layout()
        # Remove SubCondition in the CCNode
        self.__ccnode.RemoveSubCondition(subCondId)

class RegulatorItem(LabelBox):
    def __init__(self, name, specId, parent, orig=None):
        LabelBox.__init__(self, name, parent)

        self.__name = name
        self.__specId = specId

        # Duplicated RegulatorItems will have a reference to the original Regulator
        # item from which they were cloned. This is so that the duplicated item can
        # be better conformed to the specifications of the original instance.
        self.__orig = orig

    # For the draggable version!
    def reconfigure(self):
        if self.__orig:
            self.SetSize(self.__orig.GetSize())

    def GetSpecId(self):
        return self.__specId

    def Duplicate(self, parent=None):
        if parent == None:
            parent = self.GetParent()
        return RegulatorItem(self.__name, self.__specId, parent, self)

    def GetDraggable(self, window):
        d = self.Duplicate(window)
        d.SetSize(self.GetSize())
        return d
        
class LogicEditor(wx.Dialog):
    def __init__(self, model, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        self.__model = model
        self.__NEXT_REGID = -1
        self.__ccnode = None

        self.regs = wx.Panel(self)

        self.__regitems = wxscrolled.ScrolledPanel(self.regs, style=wx.SIMPLE_BORDER)
        self.__regibox  = wx.BoxSizer(wx.VERTICAL)
        self.__regitems.SetSizer(self.__regibox)

        self.pos_reg = wxscrolled.ScrolledPanel(self.regs, style=wx.SIMPLE_BORDER)
        self.neg_reg = wxscrolled.ScrolledPanel(self.regs, style=wx.SIMPLE_BORDER)

        self.__regitems.SetBackgroundColour('white')
        self.pos_reg.SetBackgroundColour('white')
        self.neg_reg.SetBackgroundColour('white')

        self.__posregbox = wx.BoxSizer(wx.VERTICAL)
        self.pos_reg.SetSizer(self.__posregbox)
        
        self.__negregbox = wx.BoxSizer(wx.VERTICAL)
        self.neg_reg.SetSizer(self.__negregbox)

        pos_lbl_box = LabelBox( 'Positive Regulators', self.pos_reg )
        self.__posregbox.Add(pos_lbl_box, 0, wx.EXPAND)
        
        neg_lbl_box = LabelBox( 'Negative Regulators', self.neg_reg )
        self.__negregbox.Add(neg_lbl_box, 0, wx.EXPAND)

        reg_size = wx.BoxSizer(wx.HORIZONTAL)
        reg_size.Add(self.__regitems, 1, wx.EXPAND)
        reg_size.Add(self.pos_reg, 2, wx.EXPAND)
        reg_size.Add(self.neg_reg, 2, wx.EXPAND)
        self.regs.SetSizer(reg_size)

        ok_button = wx.Button(self, wx.ID_OK, 'OK')

        le_size = wx.BoxSizer(wx.VERTICAL)
        le_size.Add(self.regs, 1, wx.EXPAND)
        le_size.Add(ok_button, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.SetSizer(le_size)

        # Config DragNDrop API
        self.DragNDrop = dragndrop.DragNDrop(self)

        def cfg_listener(obj, evt_type, handler):
            obj.Bind(evt_type, handler)
            for i in obj.GetChildren():
                cfg_listener( i, evt_type, handler )

        # CONFIG DRAG N DROP
        specmap = self.__model['speciesMap']
        for specId in specmap.keys():
            regitem = RegulatorItem(specmap[specId]['name'], int(specId), self.__regitems)
            cfg_listener(regitem, wx.EVT_LEFT_DOWN, self.__regitem_set_focus)
            self.DragNDrop.MakeDraggable(regitem, regitem.GetSpecId())
            self.__regibox.Add(regitem, 0, wx.EXPAND | wx.ALL, 5)
        self.__regitems.SetupScrolling(scroll_x = False)
        
        self.DragNDrop.MakeDropTarget(self.pos_reg, self.__posreg_drop)
        self.DragNDrop.MakeDropTarget(self.neg_reg, self.__negreg_drop)
        # END CONFIG DRAG N DROP

        self.regs.Bind(EVT_REGULATOR_REMOVED, self.__reg_removed)
        self.Bind(EVT_RELAYOUT, self.relayout)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)

        self.SetMinSize( (550, 450) )

        self.Centre()

    def GetCCNode(self):
        return self.__ccnode

    def relayout(self, evt):
        self.pos_reg.FitInside()
        self.neg_reg.FitInside()
        
        self.pos_reg.SetupScrolling(scroll_x = False)
        self.neg_reg.SetupScrolling(scroll_x = False)

    def __reg_removed(self, evt):
        if not evt.positive:
            return
        for i in self.neg_reg.GetChildren():
            if isinstance(i, RegulatorBox):
                wx.PostEvent(i, evt) # broadcast regulator removed event to all negative regulators

    def __regitem_set_focus(self, evt):
        self.__regitems.SetFocusIgnoringChildren()
        evt.Skip()

    def __posreg_drop(self, specId):
        if self.__ccnode.IsPosReg(specId):
            return
        specname = self.__model['speciesMap'].get(unicode(specId), {'name': 'Unknown Species'})['name']
        nextId = IDManager.NextRegulatorId()
        self.__ccnode.AddPosReg(specId, nextId)
        self.AddPositiveRegulator(specname, nextId)

        # Fire a regulator add event when a new pos reg is added so that the negative regulators will
        # adjust their dominance info
        reg_add = RegulatorAddedEvent(wx.wxEVT_NULL, reg_id=nextId, reg_name=specname)
        for i in self.neg_reg.GetChildren():
            if isinstance(i, RegulatorBox):
                wx.PostEvent(i, reg_add)

    def __negreg_drop(self, specId):
        if self.__ccnode.IsNegReg(specId):
            return
        specname = self.__model['speciesMap'].get(unicode(specId), {'name': 'Unknown Species'})['name']
        nextId = IDManager.NextRegulatorId()
        self.__ccnode.AddNegReg(specId, nextId)
        self.AddNegativeRegulator(specname, nextId, True)

    def AddPositiveRegulator(self, name, regId):
        rbox = RegulatorBox(name, True, self.pos_reg, self.__ccnode, regId, self.__model, self.DragNDrop)
        self.__posregbox.Add(rbox, 0, wx.EXPAND | wx.ALL, 5)
        self.pos_reg.SetupScrolling(scroll_x = False)
        self.__posregbox.Layout()

        return rbox

    def AddNegativeRegulator(self, name, regId, dropped=False):
        rbox = RegulatorBox(name, False, self.neg_reg, self.__ccnode, regId, self.__model, self.DragNDrop)
        self.__negregbox.Add(rbox, 0, wx.EXPAND | wx.ALL, 5)
        self.neg_reg.SetupScrolling(scroll_x = False)
        self.__negregbox.Layout()

        if dropped:
            specmap = self.__model['speciesMap']
            regmap = self.__model['regulatorMap']
            prn = self.__ccnode.GetPosRegData()
            if len(prn) == 0:
                rbox._no_doms()
            else:
                for j in prn:
                    rbox._add_dom(j[2], specmap[unicode(j[3])]['name'])

        return rbox

    def LoadLogic(self, node):
        ccnode = node.GetCCNode().Duplicate()
        self.__ccnode = ccnode

        prn = ccnode.GetPosRegIds()
        nrn = ccnode.GetNegRegIds()

        specmap = self.__model['speciesMap']
        regmap  = self.__model['regulatorMap']

        for i in nrn:
            name = specmap[unicode(regmap[unicode(i)]['regulatorSpeciesId'])]['name']
            regbox = self.AddNegativeRegulator(name, i)
            if len(prn) == 0:
                regbox._no_doms()
            else:
                dom_set = ccnode.GetDominances(i)
                for j in prn:
                    regbox._add_dom(j, specmap[unicode(regmap[unicode(j)]['regulatorSpeciesId'])]['name'], j in dom_set)
            conditions = ccnode.GetConditions(i)
            for condition in conditions:
                regbox.AddCondition([specmap[unicode(sid)]['name'] for sid in condition[5]], condition[3], condition[1].startswith("not"), condition[2],
                                    condition[0], self.__model, self.DragNDrop)
                subconds = ccnode.GetSubConditions(condition[0])
                for subcond in subconds:
                    regbox.AddSubCondition([specmap[unicode(sid)]['name'] for sid in subcond[4]], subcond[3], subcond[1].startswith("not"), subcond[2],
                                           condition[0], subcond[0], self.__model, self.DragNDrop)

        for i in prn:
            name = specmap[unicode(regmap[unicode(i)]['regulatorSpeciesId'])]['name']
            regbox = self.AddPositiveRegulator(name, i)
            conditions = ccnode.GetConditions(i)
            for condition in conditions:
                regbox.AddCondition([specmap[unicode(sid)]['name'] for sid in condition[5]], condition[3], condition[1].startswith("not"), condition[2],
                                    condition[0], self.__model, self.DragNDrop)
                subconds = ccnode.GetSubConditions(condition[0])
                for subcond in subconds:
                    regbox.AddSubCondition([specmap[unicode(sid)]['name'] for sid in subcond[4]], subcond[3], subcond[1].startswith("not"), subcond[2],
                                           condition[0], subcond[0], self.__model, self.DragNDrop)

        self.Fit()
        self.Centre()

        self.pos_reg.SetupScrolling(scroll_x = False)
        self.neg_reg.SetupScrolling(scroll_x = False)

        # Add Necessary DragNDrop event listeners to new widgets
        self.DragNDrop.Reconfigure()

class MutationDialog(wx.Dialog):
    def __init__(self, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)
        
        self.Setup = wx.Panel(self)
        protlbl = wx.StaticText(self.Setup, label="Protein:")
        self.Proteins = wx.Choice(self.Setup, style=wx.CB_SORT)
        AddMutation = wx.Button(self, wx.ID_ANY, label="Add Mutation")
        self.MutationList = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.__ok = wx.Button(self, wx.ID_ANY, "OK")

        self.__ids = {}
        self.__selected = []

        setup_boxer = wx.BoxSizer(wx.HORIZONTAL)

        setup_boxer.Add(protlbl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        setup_boxer.Add(self.Proteins, 0, wx.ALL | wx.ALIGN_CENTER, border=5)

        self.Setup.SetSizer(setup_boxer)

        boxer = wx.BoxSizer(wx.VERTICAL)

        boxer.Add(self.Setup, 0, wx.ALL | wx.EXPAND, border=5)
        boxer.Add(AddMutation, 0, wx.ALL | wx.ALIGN_CENTER, border=5)
        boxer.Add(self.MutationList, 1, wx.TOP | wx.EXPAND, border=5)
        boxer.Add(self.__ok, 0, wx.ALL | wx.ALIGN_CENTER, border = 8)

        self.SetSizer(boxer)

        self.Center()

        self.MutationList.AppendColumn("Protein")
        self.MutationList.AppendColumn("Mutation State")

        self.MutationList.SetColumnWidth(0, 300)
        self.MutationList.SetColumnWidth(1, 93)

        self.__popup = wx.Menu()
        self.__always_on  = self.__popup.Append(wx.ID_ANY, "Always On")
        self.__always_off = self.__popup.Append(wx.ID_ANY, "Always Off")
        self.__remove_mut = self.__popup.Append(wx.ID_ANY, "Remove Mutation")

        self.__index = 0

        self.Bind(wx.EVT_BUTTON, self.__add_mutation, AddMutation)
        self.__ok.Bind(wx.EVT_BUTTON, self.__close)
        self.Bind(wx.EVT_MENU, self.__set_always_on, self.__always_on)
        self.Bind(wx.EVT_MENU, self.__set_always_off, self.__always_off)
        self.Bind(wx.EVT_MENU, self.__remove_mutation, self.__remove_mut)
        self.MutationList.Bind(wx.EVT_CONTEXT_MENU, self.__do_popup_menu)

    def __do_popup_menu(self, evt):
        self.PopupMenu( self.__popup )

    def __close(self, evt=None):
        self.Close()

    def __set_always_on(self, evt):
        if self.MutationList.GetSelectedItemCount() >= 0:
            ind = self.MutationList.GetNextSelected(-1)
            self.MutationList.SetItem(ind, 1, "Always On")

    def __set_always_off(self, evt):
        if self.MutationList.GetSelectedItemCount() >= 0:
            ind = self.MutationList.GetNextSelected(-1)
            self.MutationList.SetItem(ind, 1, "Always Off")

    def __remove_mutation(self, evt):
        if self.MutationList.GetSelectedItemCount() >= 0:
            ind = self.MutationList.GetNextSelected(-1)
            data = self.MutationList.GetItemData(ind)
            self.__selected.remove(data)
            self.MutationList.DeleteItem(ind)
            self.RefreshNodeBox()
            self.Proteins.SetSelection(self.__idlist.index(data))

    def __add_mutation(self, evt=None):
        sel = self.Proteins.GetSelection()
        nid = self.__idlist[self.Proteins.GetSelection()]
        self.__add_mutation_by_id(nid, "Always On")
        self.Proteins.SetSelection(max(sel-1, 0))

    def __add_mutation_by_id(self, nid, mut_type, refresh=True):
        self.MutationList.Append((self.__ids[nid], mut_type))
        self.MutationList.SetItemData( self.MutationList.GetItemCount()-1, nid )
        self.__selected.append(nid)
        if refresh:
            self.RefreshNodeBox()

    def RefreshNodeBox(self):
        lst = []
        for i in self.__ids.keys():
            if not i in self.__selected:
                lst.append((self.__ids[i], i))
        lst.sort(key=lambda x: x[0].lower())
        self.Proteins.Clear()
        self.Proteins.SetItems([data[0] for data in lst])
        self.__idlist = [data[1] for data in lst]

    def SetupDialog(self, env, mut={}):
        e = env.values()
        for i in xrange(0, len(e)):
            node = e[i]
            self.__ids[node.speciesId] = node.name

        self.RefreshNodeBox()
        self.Proteins.SetSelection(0)
        
        for i in mut.keys():
            mut_type = "Always On"
            if mut[i] == '0':
                mut_type = "Always Off"
            self.__add_mutation_by_id(i, mut_type, False) # force "no refresh" until all mutations are added

        self.RefreshNodeBox()
        self.Proteins.SetSelection(0)

    def GetMutationSet(self):
        mut_set = {}
        for i in xrange(0,self.MutationList.GetItemCount()):
            if self.MutationList.GetItemText(i, 1) == "Always On":
                mut_set[self.MutationList.GetItemData(i)] = '1'
            else:
                mut_set[self.MutationList.GetItemData(i)] = '0'
        return mut_set

class ListManager(wx.Dialog):
    def __init__(self, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        __nmpn = wx.Panel(self)
        __nmlb = wx.StaticText(__nmpn, wx.ID_ANY, label="List Name:")
        self.__name = wx.TextCtrl(__nmpn, wx.ID_ANY, value="List")

        nmbx = wx.BoxSizer(wx.HORIZONTAL)
        nmbx.Add(__nmlb, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        nmbx.Add(self.__name, 1, wx.ALL | wx.EXPAND, border=5)

        __nmpn.SetSizer(nmbx)

        addlbl = wx.StaticText(self, wx.ID_ANY, label="Items to add to list:")
        
        self.__clb  = wx.CheckListBox(self)
        self.__ok   = wx.Button(self, wx.ID_ANY, label="OK")

        box = wx.BoxSizer(wx.VERTICAL)

        box.Add(__nmpn, 0, wx.EXPAND)
        box.Add(addlbl, 0, wx.ALL | wx.EXPAND, border=7)
        box.Add(self.__clb, 1, wx.EXPAND)
        box.Add(self.__ok, 0, wx.ALL | wx.ALIGN_CENTER, border=7)

        self.__ok.Bind(wx.EVT_BUTTON, self.__close)
        self.__name.Bind(wx.EVT_KEY_UP, self.__check_enter)

        self.__data = {}

        self.SetSizer(box)

        self.Centre()

    def __check_enter(self, evt):
        if evt.GetUnicodeKey() == wx.WXK_RETURN:
            self.__close()
        evt.Skip()

    def __close(self, evt=None):
        self.EndModal(wx.ID_OK)

    def Append(self, item):
        self.__clb.Append(item)

    def SetData(self, key, value):
        self.__data[key] = value

    def GetData(self, key):
        return self.__data[key]

    def GetItemCount(self):
        return self.__clb.GetCount()

    def GetCheckedItems(self):
        return self.__clb.GetCheckedItems()

    def SetCheckedItems(self, ilist):
        self.__clb.SetCheckedItems(ilist)

    def SetChecked(self, item):
        ci = list(self.__clb.GetCheckedItems())
        ci.extend([item])
        self.SetCheckedItems(ci)
        
    def SetName(self, name):
        self.__name.SetValue(name)
        
    def GetName(self):
        return self.__name.GetValue()

    def GetIndexByData(self, data):
        for i in xrange(0, self.__clb.GetCount()):
            if self.GetData(i) == data:
                return i
        return -1

    def LoadList(self, lst):
        self.__clb.SetCheckedStrings(lst)
