# Drag and Drop API

import wx

class DragNDrop:
    def __init__(self, window):
        self.__dragging = None
        self.__wxdragging = None

        self.__win = window

        # Track event-bound components
        self.__configured = []

        # Track drop-target handlers
        self.__drop = {}

        self.__add_mouse_list(window)

    def OnLeaveWindow(self, evt):
        if self.__wxdragging == None:
            return
        self.__wxdragging.Hide()
        self.__wxdragging = None
        self.__dragging = None

    # Make Components Draggable
    def MakeDraggable(self, wxdraggable, val, master=None):
        if master == None:
            if not hasattr(wxdraggable, 'GetDraggable'):
                raise TypeError("Cannot make a non-subclass of Draggable draggable!")
            master_win = wxdraggable.GetDraggable(self.__win)
            master_win.Hide() # instantly hide the draggable!!!
            def func(evt):
                self.Drag(master_win, val, evt)
                evt.Skip()
        else:
            master_win = master
            def func(evt):
                self.Drag(master, val, evt)
                evt.Skip()
        wxdraggable.Bind(wx.EVT_LEFT_DOWN, func)
        for i in wxdraggable.GetChildren():
            self.MakeDraggable(i, val, master_win)

    def Drag(self, wxobj, value, evt):
        self.__wxdragging = wxobj
        sz = wxobj.GetSize()
        _pos = evt.GetEventObject().ClientToScreen(evt.GetPosition())
        offs = self.__win.ClientToScreen((0,0))
        pos = (_pos[0] - offs[0], _pos[1] - offs[1])
        self.__wxdragging.SetPosition((pos[0] - (sz[0] / 2), pos[1] - (sz[1] / 2)))
        self.__wxdragging.Show()
        self.__dragging = value

    # Make a Panel a drop target

    def MakeDropTarget(self, target, handler):
        self.__drop[target] = handler

    # Add motion listener to every component in win recursively
    # (since Mouse Events are stupid command events)

    def Reconfigure(self):
        # Add motion listener to new components
        self.__add_mouse_list(self.__win, True)
                    
    def __add_mouse_list(self, win, do_reconfig=False):
        if not win in self.__configured:
            win.Bind(wx.EVT_MOTION, self.__motion_listener)
            win.Bind(wx.EVT_LEFT_UP, self.__mouse_up)
            self.__configured.append(win)
        if hasattr(win, 'reconfigure') and callable(win.reconfigure):
            win.reconfigure()
        for i in win.GetChildren():
            self.__add_mouse_list(i)

    def __getwidgetat(self, pos, widget=None):
        if widget == None:
            widget = self.__win
            
        mpos = self.__win.ClientToScreen(pos)
        for i in widget.GetChildren():
            wpos = i.GetParent().ClientToScreen(i.GetPosition())
            tpos = (mpos[0] - wpos[0], mpos[1] - wpos[1])
            sz = i.GetSize()
            
            if tpos[0] < 0 or tpos[0] > sz[0]:
                continue
            if tpos[1] < 0 or tpos[1] > sz[1]:
                continue

            if len(widget.GetChildren()) == 0:
                return widget
            else:
                return self.__getwidgetat(pos, i)
            
        return widget
            
    def __mouse_up(self, evt):
        if self.__wxdragging != None:
            sz = self.__wxdragging.GetSize()
            pos = self.__wxdragging.GetPosition()
            pos = (pos[0] + (sz[0] / 2), pos[1] + (sz[1] / 2))
            widget = self.__getwidgetat(pos)
            cur = widget
            while cur != None:
                # Go up the tree of widgets until we reach
                # a top-level window or run into a drop target
                if cur in self.__drop.keys():
                    handler = self.__drop[cur]
                    apply(handler, [self.__dragging])
                    break
                cur = cur.GetParent()
            self.__dragging = None
            self.__wxdragging.Hide()
            self.__wxdragging = None

        # Cuz there's other stuff that needs to happen
        evt.Skip()

    def __motion_listener(self, evt):
        source = evt.GetEventObject()
        pos = source.ClientToScreen(evt.GetPosition())
        spos = self.__win.ClientToScreen((0,0))
        pos = (pos[0] - spos[0], pos[1] - spos[1])
        if self.__wxdragging != None:
            sz = self.__wxdragging.GetSize()
            self.__wxdragging.SetPosition((pos[0] - (sz[0] / 2), pos[1] - (sz[1] / 2)))
            self.__wxdragging.Refresh()
        
