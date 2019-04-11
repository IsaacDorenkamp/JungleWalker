import ctypes
import os

import math
import random
import wx
import wx.grid as wxgrid
import wx.lib.scrolledpanel as wxscrolled
import wx.lib.newevent as wxevent

from modellib import *

import threading

# Registering events

UpdateMonitorEvent, EVT_UPDATE_MONITOR = wxevent.NewEvent()
RangeSliderEvent, EVT_RANGE_SLIDER = wxevent.NewEvent()

EXTENT_STRING = 'abcdefghijklmnopqrstuvwxyz'
EXTENT_STRING += EXTENT_STRING.upper() + '0123456789'

class Colors:
    EXTERNAL_NODE = wx.Colour('#f39c11')
    INTERNAL_NODE = wx.Colour('#808080')
    SELECTED_NODE = wx.Colour('#3598db')

    NODE_LABEL = wx.Colour('#acacac')

    OUT_OF_BOUNDS = wx.Colour('#e7e7e7')

class Fonts:
    try:
        NODE_FONT = wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Ubuntu")
    except Exception as e:
        print('Error Configuring Fonts: %s' % str(e))
        NODE_FONT = None

class ZoomBox:
    ZOOM_UNITS = 35
    MAX_ZOOM_LEVEL = 9
    
    def __init__(self, bottom=-5, left=-5, top=5, right=5):
        self.bottom = bottom
        self.left = left
        self.top = top
        self.right = right

    def SetBottom(self, bottom):
        self.bottom = bottom

    def SetTop(self, top):
        self.top = top

    def SetLeft(self, left):
        self.left = left

    def SetRight(self, right):
        self.right = right

    def __str__(self):
        return "bottom: %.2f, top: %.2f, left: %.2f, right: %.2f" % (self.bottom, self.top, self.left, self.right)
        
class ComponentGraph(wx.Panel):
    NODE_WIDTH = 4
    NODE_MAX_WIDTH = 7
    NODE_FONT_SIZE = 9
    NODE_MAX_FONT_SIZE = 14
    
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.SetBackgroundColour('white')

        self.Bind(wx.EVT_PAINT, self.__onpaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)

        self.nodes = {}

        self.left = -5
        self.right = 5
        self.bottom = -5
        self.top = 5

        self.__setwidth(ComponentGraph.NODE_WIDTH)

        self.zoombox = ZoomBox(self.bottom, self.left, self.top, self.right)

        # events

        self.Bind(wx.EVT_SIZE, self.__onresize)

        self.__mousemap = (-1, -1)
        self.__moved = False
        self.__selection = -1
        self.__zoomlevel = 0

        self.Bind(wx.EVT_MOUSEWHEEL, self.__onmousewheel)
        self.Bind(wx.EVT_LEFT_DOWN, self.__onmousedown)
        self.Bind(wx.EVT_LEFT_UP, self.__onmouseup)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.__onwinleave)
        self.Bind(wx.EVT_MOTION, self.__onmousemove)

    def __setwidth(self, w):
        self.__width = w
        self.__margin = 2*w

    def ToGraphCoords(self, coords):
        size = float(min(self.GetSize())) - 2*self.__margin
        return ( coords[0] - (float(self.GetSize()[0] - size) / 2) + self.__margin, coords[1] - (float(self.GetSize()[1] - size) / 2) + self.__margin )

    def ToNodeMapCoords(self, gcoords):
        """
        ToNodeMapCoords(graph_coords)
        Return the location of the mouse pointer in the NODE MAP given the coordinates WITHIN the graph space.
        """
        size = min(self.GetSize())
        zbox_xpos = ((float(gcoords[0]) / size) * (self.zoombox.right - self.zoombox.left)) + self.zoombox.left
        zbox_ypos = self.zoombox.top - ((float(gcoords[1]) / size) * (self.zoombox.top - self.zoombox.bottom))
        return (zbox_xpos, zbox_ypos)

    def GetNodeAt(self, graph_coords):
        size = min(self.GetSize())
        rsize = size + (self.__margin*2)
        for i in self.nodes.keys():
            node = self.nodes[i]
            margin_x = ((self.zoombox.right - self.zoombox.left) / rsize) * self.__margin
            margin_y = ((self.zoombox.top - self.zoombox.bottom) / rsize) * self.__margin
            if not ((node[0][0] + 2*margin_x >= self.zoombox.left and node[0][0] - 2*margin_x <= self.zoombox.right)
                    and (node[0][1] - 2*margin_y <= self.zoombox.top and node[0][1] + 2*margin_y >= self.zoombox.bottom)):
                continue
            npos = self.NodeMapToGraphCoords( (node[0][0], node[0][1]) )
            if self.__dist( npos, graph_coords ) <= self.__width:
                return node

        return None

    def InBounds(self, coords):
        size = min(self.GetSize())
        return not (coords[0] < 0 or coords[1] < 0 or coords[0] > size or coords[1] > size)

    def __dist(self, point1, point2):
        return math.sqrt( (float(point2[0]) - point1[0])**2 + (float(point2[1]) - point1[1])**2 )

    def __onresize(self, evt):
        wx.CallAfter(self.Refresh)

    def __onmousewheel(self, evt):
        l = float(evt.GetWheelRotation()) / 120 # use float for mouse "wheels" that don't emit rotation events in discrete multiples of 120
        size = float(min(self.GetSize()))
        adjx, adjy = self.ToGraphCoords( evt.GetPosition() )
        if not self.InBounds((adjx, adjy)):
            return
        node = self.GetNodeAt((adjx, adjy))
        if node != None:
            nx, ny = self.NodeMapToGraphCoords(node[0])
            px = ((float(nx) / size) * (self.zoombox.right - self.zoombox.left)) + self.zoombox.left
            py = self.zoombox.top - ((float(ny) / size) * (self.zoombox.top - self.zoombox.bottom))
        else:
            px = ((float(adjx) / size) * (self.zoombox.right - self.zoombox.left)) + self.zoombox.left
            py = self.zoombox.top - ((float(adjy) / size) * (self.zoombox.top - self.zoombox.bottom))
        unitsx = l * ZoomBox.ZOOM_UNITS * (float(self.right - self.left) / size)
        unitsy = l * ZoomBox.ZOOM_UNITS * (float(self.top - self.bottom) / size)
        nX1 = px - (float((self.zoombox.right - self.zoombox.left - unitsx)*(px-self.zoombox.right))/(self.zoombox.right - self.zoombox.left))
        nx1 = px - (float((px-nX1)*(px-self.zoombox.left))/(px-self.zoombox.right))
        if nX1 > self.right:
            nX1 = self.right
        if nx1 < self.left:
            nx1 = self.left
            
        # Our goal is to maintain the unit-width to unit-height ratio, and as such, maintain the position of the
        # location on the node map under the mouse pointer
        if nX1 - nx1 == self.right - self.left:
            nY1 = self.top
            ny1 = self.bottom
        else:
            ratio = float(self.zoombox.top - self.zoombox.bottom) / (self.zoombox.right - self.zoombox.left)
            height = ratio*(nX1 - nx1)
            seg_length = float(py - self.zoombox.top) * (height / (self.zoombox.top - self.zoombox.bottom))
            nY1 = min(py - seg_length, self.top)
            ny1 = max(nY1 - height, self.bottom)

        if l > 0 and self.__zoomlevel >= ZoomBox.MAX_ZOOM_LEVEL:
            return

        do_zoom = float(self.zoombox.right - self.zoombox.left) / (self.right - self.left) <= 0.6
        if do_zoom and l < 0:
            if abs(l) > self.__zoomlevel:
                self.__zoomlevel = 0
            else:
                self.__zoomlevel += l
        
        self.zoombox.left = float(nx1)
        self.zoombox.right = float(nX1)
        self.zoombox.top = float(nY1)
        self.zoombox.bottom = float(ny1)

        do_zoom = float(self.zoombox.right - self.zoombox.left) / (self.right - self.left) <= 0.6
        if do_zoom and l > 0:
            self.__zoomlevel += l

        self.__setwidth(max(min(ComponentGraph.NODE_WIDTH + self.__zoomlevel, ComponentGraph.NODE_MAX_WIDTH), ComponentGraph.NODE_WIDTH))
        
        wx.CallAfter(self.Refresh)

    def __onmousemove(self, evt):
        # Ascertain general necessary information
        adjx, adjy = self.ToGraphCoords(evt.GetPosition())
        size = min(self.GetSize())
        rsize = size + (self.__margin*2)
        do_cursor = False
        for i in self.nodes.keys():
            node = self.nodes[i]
            margin_x = ((self.zoombox.right - self.zoombox.left) / rsize) * self.__margin
            margin_y = ((self.zoombox.top - self.zoombox.bottom) / rsize) * self.__margin
            if not ((node[0][0] + 2*margin_x >= self.zoombox.left and node[0][0] - 2*margin_x <= self.zoombox.right)
                    and (node[0][1] - 2*margin_y <= self.zoombox.top and node[0][1] + 2*margin_y >= self.zoombox.bottom)):
                continue
            npos = self.NodeMapToGraphCoords( (node[0][0], node[0][1]) )
            if self.__dist( npos, (adjx, adjy) ) <= self.__width:
                do_cursor = True
                break
        if do_cursor:
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        if self.__mousemap != (-1, -1):
            self.__moved = True
            
            # Re-map mouse position onto the node map
            zbox_xpos, zbox_ypos = self.ToNodeMapCoords( (adjx, adjy) )

            # Store these zoombox size properties so that they can be held constant
            zbw = float(self.zoombox.right) - self.zoombox.left
            zbh = float(self.zoombox.top) - self.zoombox.bottom
            
            # Adjust so that the mapped location of the mouse pointer is the same as when it was when the left
            # mouse button was pressed UNLESS we have reached the edge of the map
            newl = min(max(self.left, self.zoombox.left + (self.__mousemap[0] - zbox_xpos)), self.right - zbw)
            newr = newl + zbw

            self.zoombox.left = newl
            self.zoombox.right = newr

            newt = max(min(self.top, self.zoombox.top + (self.__mousemap[1] - zbox_ypos)), self.bottom + zbh)
            newb = newt - zbh

            self.zoombox.top = newt
            self.zoombox.bottom = newb
            wx.CallAfter(self.Refresh)

    def __onmousedown(self, evt):
        self.SetFocus()
        if not self.InBounds(self.ToGraphCoords(evt.GetPosition())):
            return
        adjx, adjy = self.ToGraphCoords(evt.GetPosition())
        size = min(self.GetSize())
        # Map mouse position onto the node map
        self.__mousemap = self.ToNodeMapCoords( (adjx, adjy) )
        # Indicate that the mouse has not been moved since the mouse button was pressed.
        # This variable will be set when the mouse is moved while the mouse button is down.
        self.__moved = False

    # node map to graph coords
    def NodeMapToComponentCoords(self, coords):
        WIDTH = self.GetSize()[0]
        HEIGHT = self.GetSize()[1]
        size = min( WIDTH, HEIGHT )
        center = (WIDTH / 2, HEIGHT / 2)
        rsize = size - 2*self.__margin
        TOP_Y = (center[1] - float(size / 2)) + (self.__margin)
        LEFT_X = (center[0] - float(size / 2)) + (self.__margin)
        percent_left = float(coords[0] - self.zoombox.left) / (self.zoombox.right - self.zoombox.left)
        percent_top  = float(self.zoombox.top - coords[1]) / (self.zoombox.top - self.zoombox.bottom)
        gx = LEFT_X + (rsize * percent_left)
        gy = TOP_Y + (rsize * percent_top)

        return (gx, gy)

    def NodeMapToGraphCoords(self, coords):
        return self.ToGraphCoords(self.NodeMapToComponentCoords(coords))

    def __onwinleave(self, evt):
        self.__mousemap = (-1, -1)
    
    def __onmouseup(self, evt):
        adjx, adjy = self.ToGraphCoords(evt.GetPosition())
        if self.__moved:
            self.__mousemap = (-1, -1)
            return
        # On Click...
        self.__mousemap = (-1, -1)
        self.__selection = self.GetNodeAt((adjx, adjy))
        wx.CallAfter(self.Refresh)

    def GetZoomBox(self):
        return self.zoombox
        
    def SetVerticalLimits(self, bottom, top):
        nb = min(bottom, top)
        self.top = max(bottom, top)
        self.bottom = nb
        self.zoombox.SetTop(self.top)
        self.zoombox.SetBottom(self.bottom)

    def SetHorizontalLimits(self, left, right):
        nl = min(left, right)
        self.right = max(left, right)
        self.left = nl
        self.zoombox.SetLeft(self.left)
        self.zoombox.SetRight(self.right)

    def AddNode(self, name, position, external=False):
        self.nodes[name] = (position, external)
        self.Refresh()

    def Clear(self):
        self.__zoomlevel = 0
        self.__setwidth(ComponentGraph.NODE_WIDTH)
        self.nodes = {}
        self.Refresh()

    def __onpaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        self.render(dc)

    def render(self, dc):
        WIDTH = self.GetSize()[0]
        HEIGHT = self.GetSize()[1]
        size = min( WIDTH, HEIGHT )
        center = (WIDTH / 2, HEIGHT / 2)
        TOP_Y = (center[1] - float(size / 2)) + self.__margin
        LEFT_X = (center[0] - float(size / 2)) + self.__margin

        dc.Clear()
        
        gcdc = dc
        try:
            gcdc = wx.GCDC(dc)
        except:
            pass

        if self.right == self.left:
            return # don't do anything!!!
        
        if Fonts.NODE_FONT != None:
            f = wx.Font(Fonts.NODE_FONT)
            f.SetPixelSize( (0, min(ComponentGraph.NODE_FONT_SIZE + self.__zoomlevel - 3, ComponentGraph.NODE_MAX_FONT_SIZE)) )
            gcdc.SetFont(f)

        do_labels = float(self.zoombox.right - self.zoombox.left) / (self.right - self.left) <= 0.6
            
        for i in self.nodes.keys():
            node = self.nodes[i]
            margin_x = ((self.zoombox.right - self.zoombox.left) / size) * self.__margin
            margin_y = ((self.zoombox.top - self.zoombox.bottom) / size) * self.__margin
            if not ((node[0][0] + 2*margin_x >= self.zoombox.left and node[0][0] - 2*margin_x <= self.zoombox.right)
                    and (node[0][1] - 2*margin_y <= self.zoombox.top and node[0][1] + 2*margin_y >= self.zoombox.bottom)):
                continue
            if node == self.__selection:
                gcdc.SetPen( wx.Pen(Colors.SELECTED_NODE, 1) )
                gcdc.SetBrush( wx.Brush(Colors.SELECTED_NODE) )
            elif node[1]:
                gcdc.SetPen( wx.Pen(Colors.EXTERNAL_NODE, 1) )
                gcdc.SetBrush( wx.Brush(Colors.EXTERNAL_NODE) )
            else:
                gcdc.SetPen( wx.Pen(Colors.INTERNAL_NODE, 1) )
                gcdc.SetBrush( wx.Brush(Colors.INTERNAL_NODE) )
            node_loc = self.NodeMapToComponentCoords(node[0])
            gcdc.DrawCircle( node_loc[0], node_loc[1], self.__width )

        if do_labels:
            for i in self.nodes.keys():
                # Only draw node names if we are zoomed in at least a little bit
                node = self.nodes[i]
                
                gcdc.SetTextForeground( Colors.NODE_LABEL )
                draw_on_left = node[0][0] >= self.left + (float(self.right - self.left) / 2)
                draw_above = node[0][1] >= self.top - (float(self.top - self.bottom) / 2)
                sub = -(self.__width)
                te = gcdc.GetTextExtent(i)
                teh = te[1]
                if draw_on_left:
                    sub = te[0] + (self.__width)

                xval, yval = self.NodeMapToComponentCoords(node[0])

                xval -= sub
                yval -= (teh / 2)
                yval += (self.__width*2)*(2*(float(draw_above)-0.5))

                g_xval, g_yval = self.ToGraphCoords((xval, yval))

                if self.ToNodeMapCoords((0, g_yval + te[1]))[1] >= self.zoombox.top  or self.ToNodeMapCoords((0, g_yval))[1] <= self.zoombox.bottom:
                    continue
                if self.ToNodeMapCoords((g_xval + te[0], 0))[0] <= self.zoombox.left or self.ToNodeMapCoords((g_xval,0))[0] >= self.zoombox.right:
                    continue
                
                gcdc.DrawText(i, xval, yval)

        # Cover out-of bounds areas. This serves two functions:
        # 1) Nodes which are only partially within the drawing area will be clipped (this is the desired effect)
        # 2) Labels which overflow the drawing area will be clipped (this is an important effect)
        rsize = size - 2*self.__margin
        gcdc.SetBrush(wx.Brush(Colors.OUT_OF_BOUNDS))
        gcdc.SetPen( wx.Pen(Colors.OUT_OF_BOUNDS, 1) )
        gcdc.DrawRectangle((0, 0), (LEFT_X - self.__margin, HEIGHT))
        gcdc.DrawRectangle((LEFT_X - self.__margin + size, 0), (LEFT_X - self.__margin, HEIGHT))
        gcdc.DrawRectangle((0, 0), (WIDTH, (HEIGHT - size)/2))
        gcdc.DrawRectangle((0, (HEIGHT + size) / 2), (WIDTH, (HEIGHT - size)/2))

class LogicDiagram(wxscrolled.ScrolledPanel):
    NODE_RADIUS = 8
    
    def __init__(self, *args, **kwargs):
        wxscrolled.ScrolledPanel.__init__(self, *args, **kwargs)

        self.name = ""
        self.regulators = []
        self.test = lambda bits: True
        self.current_bitstring = ""

        self.SetupScrolling()
        self.EnableScrolling(True, False)
        
        self.Bind(wx.EVT_PAINT, self.__onpaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        self.Bind(wx.EVT_SIZE, self.__onresize)
        self.Bind(wx.EVT_IDLE, self.__onidle)
        self.Bind(wx.EVT_LEFT_DOWN, self.__check_nodes)

        self.activated = False

        self.__model = None

        self.__resized = False
        self.__did_resize = False

    def __onresize(self, evt):
        self.__resized = True
        wx.CallAfter(self.Refresh)

    def __onidle(self, evt):
        if self.__resized:
            self.__did_resize = True

    def __check_nodes(self, evt):
        # TODO: scroll stuff?
        if len(self.regulators) == 0:
            return
        mx = evt.GetX()
        my = evt.GetY()
        dc = wx.ClientDC(self)

        specmap = self.__model['speciesMap']

        nodex = self.GetSize()[0] - dc.GetTextExtent(self.name)[0] - 40
        nodey = (len(self.regulators)*20)
        (nodex, nodey) = self.CalcScrolledPosition((nodex, nodey))

        l = max([dc.GetTextExtent(specmap[unicode(i)]['name'])[0] for i in self.regulators])

        if len(self.regulators) > 1:
            height = self.GetSize()[1] - 40
            unit = float(height) / (len(self.regulators)-1)
                
            for i in xrange(0, len(self.regulators)):
                y = i*unit + 20
                (draw_x, draw_y) = self.CalcScrolledPosition((20, y))
                node_center = (draw_x + l + LogicDiagram.NODE_RADIUS + 5, draw_y)
                dist = math.sqrt( (mx - node_center[0])**2 + (my - node_center[1])**2 )
                if dist <= LogicDiagram.NODE_RADIUS:
                    nval = str( 1 - int(self.current_bitstring[i]) )
                    cb = list(self.current_bitstring)
                    cb[i] = nval
                    self.current_bitstring = ''.join(cb)
                    self.state_modified = False
                    break
        else:
            target_x = 20 + l + LogicDiagram.NODE_RADIUS + 5
            target_y = max(len(self.regulators)*20, self.GetSize()[1] / 2)
            node_center = self.CalcScrolledPosition((target_x, target_y))
            dc.SetBrush(wx.Brush('YELLOW'))
            dist = math.sqrt( (mx - node_center[0])**2 + (my - node_center[1])**2 )
            if dist <= LogicDiagram.NODE_RADIUS:
                self.current_bitstring = str( 1 - int(self.current_bitstring) )
                self.state_modified = False
        
        wx.CallAfter(self.__repaint)

    def __repaint(self):
        self.Refresh()
    
    def __onpaint(self, e=None):
        dc = wx.BufferedPaintDC(self)
        dc.Clear()
        try:
            dc = wx.GCDC(dc)
        except:
            pass # no smooth lines :(
        
        redb = wx.Brush("red")
        redp = wx.Pen("red", 1)

        if self.__did_resize:
            self.AdjustScroll()
            self.__did_resize = False
            self.__resized = False
        
        if len(self.regulators) == 0:
            dc.SetPen(redp)
            dc.SetBrush(redb)
            loc = self.GetSize()
            nx = loc[0] / 2
            ny = loc[1] / 2
            dc.DrawCircle( nx - LogicDiagram.NODE_RADIUS, ny - LogicDiagram.NODE_RADIUS, LogicDiagram.NODE_RADIUS )
            te_x = dc.GetTextExtent(self.name)[0]
            dc.DrawText( self.name, nx - LogicDiagram.NODE_RADIUS - (te_x / 2), ny + 2 )
            return
        
        greenb = wx.Brush("green")
        blackb = wx.Brush("black")
        greenp = wx.Pen("green", 1)
        blackp = wx.Pen("black", 2)
        
        theight = dc.GetTextExtent(self.name)[1]

        # Draw entry for specified node
        _nodex = self.GetSize()[0] - dc.GetTextExtent(self.name)[0] - 40
        _nodey = max(len(self.regulators)*10, self.GetSize()[1] / 2)
        (nodex, nodey) = self.CalcScrolledPosition((_nodex, _nodey))
        dc.DrawText(self.name, nodex, nodey - LogicDiagram.NODE_RADIUS)

        target_x = nodex - LogicDiagram.NODE_RADIUS - 5
        target_y = nodey

        # We need to hold off on drawing the circle till after all network lines have been drawn
        specmap = self.__model['speciesMap']

        # Draw entries for regulators
        l = max([dc.GetTextExtent(specmap[unicode(i)]['name'])[0] for i in self.regulators])

        if len(self.regulators) > 1:
            height = self.GetSize()[1] - 40
            unit = float(height) / (len(self.regulators)-1)
            if _nodey == len(self.regulators*10):
                unit = 20
                
            for i in xrange(0, len(self.regulators)):
                y = i*unit + 20
                (draw_x, draw_y) = self.CalcScrolledPosition((20, y))
                te = dc.GetTextExtent(specmap[unicode(self.regulators[i])]['name'])
                dc.DrawText(specmap[unicode(self.regulators[i])]['name'], draw_x + l - te[0], draw_y - (te[1] / 2))
                dc.SetPen(blackp)
                dc.DrawLine(draw_x + l + LogicDiagram.NODE_RADIUS + 5, draw_y, target_x, target_y)
                if self.current_bitstring[i] == '1':
                    dc.SetBrush(greenb)
                    dc.SetPen(greenp)
                else:
                    dc.SetBrush(redb)
                    dc.SetPen(redp)
                dc.DrawCircle(draw_x + l + LogicDiagram.NODE_RADIUS + 5, draw_y, LogicDiagram.NODE_RADIUS)
        else:
            te = dc.GetTextExtent(specmap[unicode(self.regulators[0])]['name'])
            dc.DrawText(specmap[unicode(self.regulators[0])]['name'], 20 + l - te[0], target_y - (te[1] / 2))
            dc.SetPen(blackp)
            dc.DrawLine(20 + l + LogicDiagram.NODE_RADIUS + 5, target_y, target_x, target_y)
            if self.current_bitstring == '1':
                dc.SetBrush(greenb)
                dc.SetPen(greenp)
            else:
                dc.SetBrush(redb)
                dc.SetPen(redp)
            dc.DrawCircle(20 + l + LogicDiagram.NODE_RADIUS + 5, target_y, LogicDiagram.NODE_RADIUS)

        # Finishing what we started
        self.activated = self.test(self.current_bitstring)
        if self.activated:
            dc.SetPen(greenp)
            dc.SetBrush(greenb)
        else:
            dc.SetPen(redp)
            dc.SetBrush(redb)
        dc.DrawCircle(target_x, target_y, LogicDiagram.NODE_RADIUS)
    
    def LoadLogic(self, node, regulators, test_func, model):
        self.name = node
        self.regulators = regulators
        self.test = test_func
        self.current_bitstring = '0'*len(regulators)
        self.__model = model

        self.AdjustScroll()
        
        self.Refresh()

    def ClearLogic(self):
        self.name = ''
        self.regulators = []
        self.test = lambda bits: True
        self.Refresh()

    def AdjustScroll(self, evt=None):
        ysize = max(len(self.regulators)*20 + 20, self.GetSize()[1])
        wx.CallAfter( self.SetScrollbars, 5, 5, self.GetSize()[0] / 5, ysize / 5 )

class TransparentStatus(wx.Panel):
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.Bind(wx.EVT_SIZE, self.__onsize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)

        self.__text = ""
        self.__margin = 12

        cdc = wx.ClientDC(self)
        cdc.SetFont(self.GetFont())
        h = cdc.GetTextExtent(EXTENT_STRING)[1]

        self.SetMinSize((0, h + 2*self.__margin))

    def __onsize(self, evt=None):
        self.Refresh()
        
    def OnErase(self, evt=None):
        pass
    
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle((0, 0), self.GetSize())
        dc.SetFont(self.GetFont())
        te = dc.GetTextExtent(self.__text)
        dc.DrawText(self.__text, self.GetSize()[0] - self.__margin - te[0], (self.GetSize()[1] / 2) - (te[1] / 2))

    def SetFont(self, fnt):
        wx.Panel.SetFont(self, fnt)
        cdc = wx.ClientDC(self)
        cdc.SetFont(fnt)
        h = cdc.GetTextExtent(EXTENT_STRING)[1]

        self.SetMinSize((0, h + 2*self.__margin))
        
    def SetText(self, txt):
        self.__text = txt
        self.Refresh()

    def GetText(self):
        return self.__text
        
class StatusPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.__progress = 100.0

        self.Bind(wx.EVT_PAINT, self.__draw)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.__onerase)
    def SetProgress(self, prog):
        if prog > 1 or prog < 0:
            raise ValueError("Progress must be between 0 and 1 (0% and 100%)!")
        self.__progress = prog
        self.Refresh()
    def GetProgress(self):
        return self.__proress

    def __onerase(self, evt):
        pass

    def __draw(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.Clear()
        dc.SetBrush(wx.GREEN_BRUSH)
        dc.SetPen(wx.GREEN_PEN)
        dc.DrawRectangle(0, 0, int(self.GetSize()[0] * self.__progress), self.GetSize()[1])
        evt.Skip()
    
class ActivityLog:
    def __init__(self):
        self.log = {}
    def Log(self, timestamp, value):
        self.log[timestamp] = value
    def Clear(self):
        self.log = {}
    def GetActivityLevel(self, timestamp):
        if not timestamp in self.log.keys():
            return -1
        return self.log[timestamp]

class ActivityMonitor(wx.Panel):
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.__brushes = {
            'black': wx.Brush('black')
        }

        self.legend = {} # Node names associated with colors
        self.log = {}
        self.last_timestamp = 0
        self.prepared = False

        self.__x = 0

        self.redraw = False

        self.ThreadLock = threading.Lock()

        self.__buffer = wx.Bitmap(self.GetSize()[0], self.GetSize()[1])
        dc = wx.BufferedDC(None, self.__buffer)
        dc.SetBackground(wx.Brush('white'))
        dc.Clear()

        self.Bind(wx.EVT_PAINT, self.__draw)
        self.Bind(wx.EVT_SIZE, self.__do_resize)
        self.Bind(EVT_UPDATE_MONITOR, self.__on_update_evt)

        self.frame = -1
        self.frame_drawn = False

    def __do_resize(self, evt):
        wx.CallAfter(self.__resize)
    def __resize(self):
        if self.GetSize()[0] == self.__buffer.GetWidth() and self.GetSize()[1] == self.__buffer.GetHeight():
            return
        update_evt = UpdateMonitorEvent(steps = -1, activity_levels = None)
        wx.PostEvent(self, update_evt)

    def PreviousFrame(self):
        if self.frame == 0:
            return
        else:
            if self.frame == -1:
                self.frame = int(math.floor(float(self.last_timestamp) / 100) - 1)
            else:
                self.frame -= 1
            self.frame_drawn = False

    def NextFrame(self):
        if self.frame == -1:
            return
        max_frame = math.floor(float(self.last_timestamp) / 100) - 1
        if self.frame < max_frame:
            self.frame += 1
        else:
            self.frame = -1
            self.redraw = True
        self.frame_drawn = False

    def Track(self, protein, color='black'):
        self.legend[protein] = color
        self.log[protein] = ActivityLog()
        wx.CallAfter(self._redraw)

    def _redraw(self):
        self.redraw = True
        self.Update(-1, None)
        self.Refresh()

    def Reset(self):
        for i in self.log.keys():
            self.log[i].Clear()

    def UnTrack(self, prot):
        if prot in self.log.keys():
            del self.legend[prot]
            del self.log[prot]
            wx.CallAfter(self._redraw)

    def GetTracking(self):
        return self.log.keys()

    def __draw_legend(self, dc):
        if len(self.legend) == 0:
            return
        total_height = 5*len(self.legend)
        for i in self.legend.keys():
            total_height += dc.GetTextExtent(i.name)[1]
        total_height += 5

        span = min(self.GetSize()[0] - 80, self.GetSize()[1] - 80)
        
        height = min(total_height, span)
        l = [dc.GetTextExtent(i.name)[0] for i in self.legend.keys()]
        if len(l) == 0:
            l.append(50)
        width = max(l) + 25

        dc.SetPen(wx.Pen('black', 2))
        dc.SetBrush(wx.Brush('white', wx.TRANSPARENT))
        dc.DrawRectangle(((self.GetSize()[0] + span) / 2) - width, ((self.GetSize()[1] + span) / 2) - span, width, height)
        cur_y = ((self.GetSize()[1] - span) / 2) + 5
        for i in self.legend.keys():
            dc.DrawText(i.name, ((self.GetSize()[0] + span) / 2) + 20 - width, cur_y)
            dc.SetBrush(wx.Brush(self.legend[i], wx.SOLID))
            theight = dc.GetTextExtent(i.name)[1]
            dc.DrawRectangle(((self.GetSize()[0] + span) / 2) - width + 5, cur_y + (theight / 2) - 4, 10, 10)
            cur_y += 5 + theight

    def __on_update_evt(self, evt):
        if evt.steps == -1:
            self.redraw = True
        wx.CallAfter(self.Update, evt.steps, evt.activity_levels)
        
    def Update(self, timestamp, vals):
        if timestamp != -1:
            self.last_timestamp = timestamp
            for i in vals.keys():
                if not i in self.log.keys():
                    continue
                self.log[i].Log(timestamp, vals[i])
        elif timestamp == -1 and not self.redraw:
            return
        x = int(max(0, math.floor(float(self.last_timestamp) / 100)*100))
        span = min(self.GetSize()[0] - 80, self.GetSize()[1] - 80)
        xaxis_y = (self.GetSize()[1] + span) / 2
        dc = wx.BufferedDC(wx.ClientDC(self), self.__buffer)
        if self.last_timestamp == 0 or x != self.__x:
            self.__x = x
            if self.frame == -1:
                dc.SetBackground(wx.Brush('white'))
                dc.Clear()
                self.__draw_axes(dc, self.__x, self.__x+100)
            else:
                self.__draw_axes(dc, self.frame*100, (self.frame*100)+100)
            self.__draw_legend(dc)
        # Draw next line on graph
        if self.frame == -1:
            if not self.redraw:
                for i in self.log.keys():
                    last_act = self.log[i].GetActivityLevel(self.last_timestamp - 1)
                    act = self.log[i].GetActivityLevel(self.last_timestamp)
                    if last_act == -1 or act == -1:
                        continue
                    last_act *= 100
                    act *= 100
                    dc.SetPen(wx.Pen(self.legend[i], 3))
                    dx = dy = float(span)/100
                    x0 = int(((self.GetSize()[0] - span) / 2) + dx*(self.last_timestamp - self.__x))
                    dc.DrawLine( x0, int(xaxis_y - (dy * last_act)), x0 + dx, int(xaxis_y - (dy * act)) )
            else:
                self.__buffer = wx.Bitmap(self.GetSize()[0], self.GetSize()[1])
                dc = wx.BufferedDC(wx.ClientDC(self), self.__buffer)
                dc.SetBackground(wx.Brush('white'))
                dc.Clear()
                self.__draw_axes(dc, x, x+100)
                for i in self.log.keys():
                    for j in xrange( x, self.last_timestamp+1 ):
                        last_act = self.log[i].GetActivityLevel(j - 1)
                        act = self.log[i].GetActivityLevel(j)
                        if last_act == -1 or act == -1:
                            continue
                        last_act *= 100
                        act *= 100
                        dc.SetPen(wx.Pen(self.legend[i], 3))
                        dx = dy = float(span)/100
                        x0 = int(((self.GetSize()[0] - span) / 2) + dx*(j - x))
                        dc.DrawLine( x0, int(xaxis_y - (dy * last_act)), x0 + dx, int(xaxis_y - (dy * act)) )
                self.__draw_legend(dc)
                self.redraw = False
        else:
            if self.frame > math.floor(float(self.last_timestamp) / 100) - 1:
                self.frame = -1
                self.Update(timestamp, vals)
            elif self.frame >= 0: # this condition is only reached if 0 <= self.frame < max_frame (current frame is denoted by -1)
                if not self.frame_drawn or self.redraw:
                    self.__buffer = wx.Bitmap(self.GetSize()[0], self.GetSize()[1])
                    dc = wx.BufferedDC(wx.ClientDC(self), self.__buffer)
                    dc.SetBackground(wx.Brush('white'))
                    dc.Clear()
                    self.__draw_axes(dc, self.frame*100, (self.frame*100)+100)
                    for i in self.log.keys():
                        for j in xrange( self.frame*100, (self.frame*100)+101 ):
                            last_act = self.log[i].GetActivityLevel(j - 1)
                            act = self.log[i].GetActivityLevel(j)
                            if last_act == -1 or act == -1:
                                continue
                            last_act *= 100
                            act *= 100
                            dc.SetPen(wx.Pen(self.legend[i], 3))
                            dx = dy = float(span)/100
                            x0 = int(((self.GetSize()[0] - span) / 2) + dx*(j - (self.frame*100)))
                            dc.DrawLine( x0, int(xaxis_y - (dy * last_act)), x0 + dx, int(xaxis_y - (dy * act)) )
                    self.__draw_legend(dc)
                    self.frame_drawn = True
                    self.redraw = False

    def Prepare(self):
        self.prepared = True

    def __draw(self, evt):
        if not self.prepared:
            return
        dc = wx.BufferedPaintDC(self, self.__buffer)

    def __draw_axes(self, gfx, minx, maxx):
        xspan = yspan = min(self.GetSize()[0] - 80, self.GetSize()[1] - 80)
        draw_minx = (self.GetSize()[0] - xspan) / 2
        draw_maxx = draw_minx + xspan
        xaxis_y = (self.GetSize()[1] + yspan) / 2
        gfx.SetPen(wx.Pen('black', 2))
        gfx.SetBrush(wx.Brush('black', wx.SOLID))
        f = gfx.GetFont()
        f.SetWeight(wx.FONTWEIGHT_BOLD)
        gfx.SetFont( f )
        gfx.DrawLine(draw_minx, xaxis_y, draw_maxx, xaxis_y)
        for i in xrange(0, 101, 10):
            xval = draw_minx + int((float(xspan) / 100)*i)
            gfx.DrawLine(xval, xaxis_y, xval, xaxis_y + 5)
            te = gfx.GetTextExtent(str(minx + i))
            textx = te[0]
            texty = te[1]
            #for j in xrange(0, 360, 45):
            gfx.DrawRotatedText(str(minx + i), (xval + (texty / 2) + 3, xaxis_y + 10), -90)

        # Now for the vertical axis
        gfx.DrawLine(draw_minx, xaxis_y, draw_minx, xaxis_y - xspan)
        for i in xrange(0, 101, 10):
            yval = xaxis_y - int((float(xspan) / 100)*i)
            gfx.DrawLine(draw_minx, yval, draw_minx - 5, yval)
            te = gfx.GetTextExtent(str(i))
            textx = te[0]
            texty = te[1]
            gfx.DrawText(str(i), draw_minx - textx - 10, yval - (texty / 2))
    
class TruthTable(wxgrid.Grid):
    def __init__(self, *args, **kwargs):
        wxgrid.Grid.__init__(self, *args, **kwargs)
        self.CreateGrid(0,0)
        self.SetCellHighlightPenWidth(0)
        self.SetCellHighlightROPenWidth(0)
        self.EnableEditing(False)
        self.DisableDragColMove()
        self.DisableDragColSize()
        self.DisableDragRowSize()

        self.SetRowLabelSize(1)
        self.SetColLabelSize(1)

        self.SetDefaultCellBackgroundColour('#EEEEEE')

        self.__padding = 0

        self.__model = None
        self.prot = None

    def SetModel(self, model):
        self.__model = model

    def SetPadding(self, pad):
        self.__padding = pad

    def GetPadding(self):
        return self.__padding

    def ClearTable(self):
        if self.GetNumberRows() > 0:
            self.DeleteRows(0, self.GetNumberRows())
        if self.GetNumberCols() > 0:
            self.DeleteCols(0, self.GetNumberCols())

    def FixSizes(self):
        # here, the program will equalize column sizes, and fit them in the container.
        # however, later on, it will proceed to extend the width of those columns for
        # which the first-row cells cannot fit the protein name properly.
        prot = self.prot
        if prot == None:
            return
        for i in xrange(0, prot.TotalRegulators()+1):
            sz = max((self.GetParent().GetSize()[0] - (4*self.__padding)) / (prot.TotalRegulators()+1), 0)
            self.SetColSize(i, math.floor(sz))

        c = wx.ClientDC(self)
        c.SetFont(self.GetDefaultCellFont())
        for i in xrange(0, prot.TotalRegulators()+1):
            lcs = self.GetColSize(i)
            while c.GetTextExtent(self.GetCellValue(0, i))[0] + 5 > self.GetColSize(i):
                lcs = self.GetColSize(i)
                self.SetColSize(i, self.GetColSize(i)+1)
                if lcs == self.GetColSize(i):
                    break

    def DisplayTable(self, prot):
        if self.__model == None:
            return
        
        if prot.TotalRegulators() > 13:
            raise ValueError("This protein has too many regulators (%d) to display its truth table. Use the Condition Tester to learn about its behavior." % prot.TotalRegulators())

        self.prot = prot

        self.ClearGrid()
        self.ClearTable()

        desired_rows = (2**prot.TotalRegulators())+1
        desired_cols = prot.TotalRegulators()+1

        self.AppendRows(desired_rows)
        self.AppendCols(desired_cols)

        specmap = self.__model['speciesMap']

        for i in xrange(0, prot.TotalRegulators()):
            self.SetCellValue(0, i, specmap[unicode(prot.regulators[i])]['name'])

        self.SetCellValue(0, prot.TotalRegulators(), prot.name)

        for i in xrange(0, (2**prot.TotalRegulators())):
            bitstring = bin(i)[2:].zfill(prot.TotalRegulators())
            for j in xrange(0, len(bitstring)):
                self.SetCellValue(i+1, j, bitstring[j])
            self.SetCellValue(i+1, prot.TotalRegulators(), str(prot.truth_table[bitstring]))

        self.FixSizes()

        for i in xrange(0, (2**prot.TotalRegulators())+2):
            self.SetCellBackgroundColour(i, prot.TotalRegulators(), '#dddddd')

class SliderSetDialog(wx.Dialog):
    def __init__(self, parent, title, sval):
        wx.Dialog.__init__(self, parent, title=title);
        lbl  = wx.StaticText(self, label="New Value:")
        self.__spin = wx.SpinCtrl(self, min=0, max=100, style=wx.ALIGN_CENTER | wx.TE_PROCESS_ENTER)
        ok = wx.Button(self, wx.ID_OK, label="OK")

        gbs = wx.GridBagSizer()

        gbs.Add( lbl, pos=(0, 0), flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5 )
        gbs.Add( self.__spin, pos=(0, 1), flag=wx.EXPAND )
        gbs.Add( ok, pos=(1, 0), span=(1, 2), flag=wx.EXPAND )

        self.__spin.SetValue(sval)

        self.__spin.Bind(wx.EVT_SET_FOCUS, self.__select)
        self.__spin.Bind(wx.EVT_TEXT_ENTER, self.__doclose)

        self.SetSizer(gbs)
        self.Fit()
        self.Centre()

    def __select(self, evt):
        e = evt.GetEventObject()
        e.SetSelection(0, len(str(e.GetValue())))
        evt.Skip()

    def __doclose(self, evt):
        self.EndModal(wx.ID_OK)

    def GetValue(self):
        return self.__spin.GetValue()
        
class SliderListItem:
    def __init__(self, parent, name, label):
        self.label = wx.StaticText(parent, label=label)
        self.display = wx.StaticText(parent, label="0%")
        self.slider = wx.Slider(parent)

        self.name = name
        self.__click = False

        self.slider.Bind(wx.EVT_SLIDER, self.__on_slider, self.slider)
        self.display.Bind(wx.EVT_LEFT_UP, self.__check_click)
        self.display.Bind(wx.EVT_LEFT_DOWN, self.__set_click)
        self.display.Bind(wx.EVT_LEAVE_WINDOW, self.__unset_click)
    
    def __set_click(self, evt):
        self.__click = True
    def __unset_click(self, evt):
        self.__click = False
    def __check_click(self, evt):
        if self.__click:
            sd = SliderSetDialog(None, self.label.GetLabel(), self.slider.GetValue())
            sd.ShowModal()
            self.slider.SetValue(sd.GetValue())
            self.__on_slider()
            self.__click = False
            
    def __on_slider(self, evt=None):
        self.display.SetLabel("%d%%" % self.slider.GetValue())

    def GetValue(self):
        return self.slider.GetValue()
    def SetValue(self, v):
        self.slider.SetValue(v)
        self.__on_slider()
class SliderList(wx.ScrolledWindow):
    def __init__(self, parent, randomizer=False):
        wx.ScrolledWindow.__init__(self, parent, style=wx.SIMPLE_BORDER)

        self.__randomizer = randomizer

        self.__items = []
        self.__specs = []
        self.__sizer = wx.FlexGridSizer(rows=0, cols=3, hgap=0, vgap=5)

        self.SetSizer(self.__sizer)
        
        if randomizer:
            self.rand_btn = wx.Button(self, label="Randomize")
            self.rand_btn.Bind(wx.EVT_BUTTON, self.Randomizer)

            self.__sizer.Add(wx.Panel(self))
            self.__sizer.Add(self.rand_btn, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
            self.__sizer.Add(wx.Panel(self))
        else:
            self.rand_btn = None

        self.ShowScrollbars(wx.SHOW_SB_DEFAULT, wx.SHOW_SB_DEFAULT)
        self.SetScrollRate(3, 12)

        self.Bind(wx.EVT_CHILD_FOCUS, self.__focus_on_me)

    def Randomizer(self, evt):
        for i in self.__items:
            i.SetValue(random.randint(0, 100))

    def __focus_on_me(self, evt):
        if evt.GetEventObject() == self.rand_btn:
            return
        self.SetFocusIgnoringChildren()

    def GetSizer(self):
        return self.__sizer

    def Append(self, name, specId, label=None):
        if label == None:
            label = name
        for i in self.__items:
            if i.name == name:
                raise ValueError("Name '%s' already exists in list!" % name)
        litem = SliderListItem(self, name, label)
        self.__items.append( litem )
        self.__specs.append( specId )
        
        self.__sizer.Add(litem.label, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
        self.__sizer.Add(litem.slider, flag=wx.ALL, border=10)
        self.__sizer.Add(litem.display, flag=wx.ALL, border=10)
        self.__sizer.Layout()
        self.FitInside()

    def GetItemNames(self):
        return [i.name for i in self.__items]
    def GetItemIds(self):
        return self.__specs
    def HasId(self, item_id):
        return item_id in self.__specs
    def HasKey(self, name):
        return name in [i.name for i in self.__items]

    def GetValue(self, specId):
        for i in xrange(0, len(self.__items)):
            if self.__specs[i] == specId:
                return self.__items[i].GetValue()
        raise ValueError("No elemented named '%s'." % name)

    def SetValue(self, specId, value):
        for i in xrange(0, len(self.__items)):
            if self.__specs[i] == specId:
                self.__items[i].SetValue(value)
                return
        raise KeyError("No item '%s' found." % name)

    def Remove(self, name):
        """Remove(name) - Remove item with specified name value"""
        del_ind = -1
        comp = None
        for i in xrange(0, len(self.__items)):
            cur = self.__items[i]
            if cur.name == name:
                comp.label.Destroy()
                comp.slider.Destroy()
                comp.display.Destroy()
                del_ind = i
                comp = cur
                break

        if comp != None:
            self.__sizer.Remove(comp.label)
            self.__sizer.Remove(comp.slider)
            self.__sizer.Remove(comp.display)
            self.__sizer.Layout()
            self.FitInside()

        del comp
        
        if del_ind >= 0:
            del self.__items[del_ind]
            del self.__specs[del_ind]

    def RemoveIndex(self, index):
        comp = self.__items[index]

        comp.label.Destroy()
        comp.slider.Destroy()
        comp.display.Destroy()

        self.__sizer.Remove(comp.label)
        self.__sizer.Remove(comp.slider)
        self.__sizer.Remove(comp.display)
        self.__sizer.Layout()
        self.FitInside()

        del comp
        del self.__items[del_ind]
        del self.__specs[del_ind]

    def Reset(self):
        for i in self.__items:
            i.SetValue(0)

    def Clear(self):
        del self.__items
        del self.__specs
        self.__items = []
        self.__specs = []

        self.__sizer.Clear(True)

        if self.__randomizer:
            self.rand_btn = wx.Button(self, label="Randomize")
            self.rand_btn.Bind(wx.EVT_BUTTON, self.Randomizer)

            self.__sizer.Add(wx.Panel(self))
            self.__sizer.Add(self.rand_btn, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
            self.__sizer.Add(wx.Panel(self))

        self.__sizer.Layout()
        
        self.FitInside()
        
class MinMax:
    def __init__(self, minval, maxval):
        self.min = minval
        self.max = maxval
    def __getitem__(self, ind):
        if ind == 0:
            return self.min
        elif ind == 1:
            return self.max
        else:
            raise IndexError("Invalid index for ordered pair: %s" % str(ind))
    def __setitem__(self, ind, value):
        if ind == 0:
            self.min = value
        elif ind == 1:
            self.max = value
        else:
            raise IndexError("Invalid index for ordered pair: %s" % str(ind))
    def __str__(self):
        return "(%d, %d)" % (self.min, self.max)

# RANGE SLIDER LIB
class RangeSlider(wx.Panel):
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        # Configure the range to allow selection from
        self.__min = 0
        self.__max = 100

        self.SetInitialSize((150,25))

        self.Bind(wx.EVT_PAINT, self.__onpaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.__onerase)

        # handle half-size
        self.__handle = 2

        # container border thickness
        self.__thickness = 3

        self.__margin = 3
        
        self.__selection = MinMax(0, 0)
        self.SetRange(self.__min, self.__max)

        # colors :)
        # I would configure these as static variables,
        # but the wx App has to be created before any
        # wx objects (including instances of Colour)
        # can be created.

        self.__skyblue = wx.Colour('#87ceeb')
        self.__skyblue_brush = wx.Brush(self.__skyblue)
        self.__skyblue_pen_thin = wx.Pen(self.__skyblue, 1)
        self.__skyblue_pen_thick = wx.Pen(self.__skyblue, self.__thickness)

        self.__black_brush = wx.Brush(wx.BLACK)
        self.__black_pen_thin = wx.Pen(wx.BLACK, 1)
        self.__black_pen_thick = wx.Pen(wx.BLACK, self.__thickness)

        self.__gray_pen_thick = wx.Pen('#bcbcbc', self.__thickness)

        self.__highlight_min = False
        self.__highlight_max = False
        self.__dragging_min = False
        self.__dragging_max = False

        self.__hover_cursor = wx.Cursor(wx.CURSOR_HAND)
        self.__arrow_cursor = wx.Cursor(wx.CURSOR_ARROW)

        self.__frame = self.GetParent()
        while self.__frame.GetParent() != None:
            self.__frame = self.__frame.GetParent()

        ### CONFIG NON-PAINT EVENTS ###
        self.Bind(wx.EVT_MOTION, self.__mouse_mv)
        self.Bind(wx.EVT_LEFT_DOWN, self.__left_down)
        self.Bind(wx.EVT_LEFT_UP, self.__left_up)
        self.Bind(wx.EVT_SIZE, self.__onsize)
        self.Bind(wx.EVT_ENTER_WINDOW, self.__endall)

    def __onsize(self, evt):
        gr = self.GetRange()
        self.SetRange(gr[0], gr[1])

    def __onerase(self, evt=None):
        pass

    def __onpaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        self.__draw(dc, evt)

    def __draw(self, dc, evt):
        width, height = self.GetClientSize()

        if not width or not height:
            return

        if width <= 2*(self.__handle + self.__thickness):
            width = 2*(self.__handle + self.__thickness) + 1 # screw dat!

        dc.Clear()
        dc.SetPen(self.__black_pen_thin)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle((0,0), self.GetSize())

        # Draw Container
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(self.__gray_pen_thick)

        dc.DrawLine(self.__thickness + self.__margin + self.__handle, (height / 2), width - 2*self.__thickness - 2*self.__margin, (height / 2))
        
        # Draw Selection Region
        dc.SetPen(self.__skyblue_pen_thick)
        dc.SetBrush(self.__skyblue_brush)

        draw_x = self.__thickness + self.__margin + self.__handle + self.__selection[0]
        internal_height = height - 2*self.__thickness
        xspan = self.__selection[1] - self.__selection[0]

        dc.DrawLine(draw_x, height / 2, draw_x + xspan, height / 2)

        # Draw Min/Max draggables
        dc.SetBrush(self.__black_brush)
        dc.SetPen(self.__black_pen_thin)
        c_drawx = draw_x - self.__handle

        dc.DrawRectangle(c_drawx, 5, self.__handle*2, internal_height - 4)
        dc.DrawRectangle(c_drawx + xspan, 5, self.__handle*2, internal_height - 4)

        #evt.Skip()

    def __endall(self, evt):
        self.__dragging_min = False
        self.__dragging_max = False
        self.__highlighting_min = False
        self.__highlighting_max = False

    def __get_internal_width(self):
        width = self.GetClientSize()[0]
        return width - 2*(self.__handle + self.__margin + self.__thickness)

    def __get_min_x(self):
        internal_width = self.__get_internal_width()
        return int(float(internal_width / (self.__max - self.__min)) * float(self.__selection[0]))
    def __get_max_x(self):
        internal_width = self.__get_internal_width()
        xspan = self.__get_xspan()
        return int(float(internal_width / (self.__max - self.__min)) * float(self.__selection[0])) + xspan

    def __mouse_mv(self, evt):
        # check for collision with max handle
        width = self.GetClientSize()[0]
        x, y = evt.GetPosition()
        if self.__dragging_min:
            proposed = evt.GetX() - self.__thickness - self.__margin
            if proposed >= 0 and proposed <= self.__selection[1]:
                self.__selection[0] = proposed
                rng = self.GetRange()
                rs_evt = RangeSliderEvent(minimum=rng[0], maximum=rng[1])
                wx.PostEvent(self, rs_evt)
            self.Refresh()
            return # delegate event handling to handler assigned to parent
        if self.__dragging_max:
            proposed = evt.GetX() - self.__thickness - self.__margin
            if evt.GetX() <= self.GetSize()[0] - self.__thickness - self.__margin - 2*self.__handle and proposed >= self.__selection[0]:
                self.__selection[1] = proposed
                rng = self.GetRange()
                rs_evt = RangeSliderEvent(minimum=rng[0], maximum=rng[1])
                wx.PostEvent(self, rs_evt)
            self.Refresh()
            return
        internal_width = self.__get_internal_width()
        refresh = False
        x = x - self.__thickness - self.__margin
        if (x >= self.__selection[1] and x <= self.__selection[1] + 2*self.__handle) and (y >= 5 and y <= self.GetSize()[1] - 5):
            # highlight the handle
            if not self.__highlight_max:
                self.__highlight_max = True
                refresh = True
        else:
            if self.__highlight_max:
                self.__highlight_max = False
                refresh = True
        if (x >= self.__selection[0] and x <= self.__selection[0] + 2*self.__handle) and (y >= 5 and y <= self.GetSize()[1] - 5) and not self.__highlight_max:
            if not self.__highlight_min:
                self.__highlight_min = True
                refresh = True
        else:
            if self.__highlight_min:
                self.__highlight_min = False
                refresh = True

        if (self.__highlight_min or self.__highlight_max) and refresh:
            self.SetCursor( self.__hover_cursor )
        elif not (self.__highlight_min or self.__highlight_max):
            if refresh:
                self.SetCursor( self.__arrow_cursor )

    def __left_down(self, evt):
        if self.__highlight_min:
            self.__dragging_min = True
        if self.__highlight_max:
            self.__dragging_max = True

    def __left_up(self, evt):
        if self.__dragging_min:
            self.__dragging_min = False
        if self.__dragging_max:
            self.__dragging_max = False

    # PUBLIC FUNCTIONS
    def GetRange(self):
        internal_width = self.__get_internal_width()

        minv = ((self.__selection[0] * (self.__max - self.__min)) / internal_width) + self.__min
        maxv = ((self.__selection[1] * (self.__max - self.__min)) / internal_width) + self.__min

        return (minv, maxv)
    
    def GetIntRange(self):
        internal_width = self.__get_internal_width()

        minv = round(((self.__selection[0] * (self.__max - self.__min)) / internal_width) + self.__min)
        maxv = round(((self.__selection[1] * (self.__max - self.__min)) / internal_width) + self.__min)

        return (int(minv), int(maxv))
    
    def SetRange(self, minimum, maximum):
        internal_width = self.__get_internal_width()
        self.__selection[0] = float(minimum-self.__min)*internal_width / (self.__max - self.__min)
        self.__selection[1] = float(maximum-self.__min)*internal_width / (self.__max - self.__min)
        self.Refresh()
        
    def GetMinimum(self):
        return self.__min
    
    def GetMaximum(self):
        return self.__max
    
class RangeSliderSetDialog(wx.Dialog):
    def __init__(self, parent, title, lowval, highval):
        wx.Dialog.__init__(self, parent, title=title)
        lbl  = wx.StaticText(self, label="New Range:")
        self.__minspin = wx.SpinCtrl(self, min=0, max=100, style=wx.ALIGN_CENTER | wx.TE_PROCESS_ENTER)
        self.__maxspin = wx.SpinCtrl(self, min=0, max=100, style=wx.ALIGN_CENTER | wx.TE_PROCESS_ENTER)
        self.__minspin.SetMaxSize((50, 50))
        self.__maxspin.SetMaxSize((50, 50))
        ok = wx.Button(self, wx.ID_OK, label="OK")

        gbs = wx.GridBagSizer()

        gbs.Add( lbl, pos=(0, 0), flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5 )
        gbs.Add( self.__minspin, pos=(0, 1), flag=wx.EXPAND )
        gbs.Add( wx.StaticText(self, wx.ID_ANY, "  -  "), pos=(0, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5 )
        gbs.Add( self.__maxspin, pos=(0, 3), flag=wx.EXPAND )
        gbs.Add( ok, pos=(1, 0), span=(1, 4), flag=wx.EXPAND )

        self.__minspin.SetValue(lowval)
        self.__maxspin.SetValue(highval)

        self.__minspin.Bind(wx.EVT_SET_FOCUS, self.__select)
        self.__maxspin.Bind(wx.EVT_SET_FOCUS, self.__select)
        self.__minspin.Bind(wx.EVT_TEXT_ENTER, self.__doclose)
        self.__maxspin.Bind(wx.EVT_TEXT_ENTER, self.__doclose)

        self.SetSizer(gbs)
        self.Fit()
        self.Centre()

    def __select(self, evt):
        e = evt.GetEventObject()
        e.SetSelection(0, len(str(e.GetValue())))
        evt.Skip()

    def __doclose(self, evt):
        self.EndModal(wx.ID_OK)

    def GetRange(self):
        if self.__minspin.GetValue() > self.__maxspin.GetValue():
            return None
        return (self.__minspin.GetValue(), self.__maxspin.GetValue())
    
class RangeSliderListItem:
    def __init__(self, parent, name, label):
        self.label = wx.StaticText(parent, label=label)
        self.display = wx.StaticText(parent, label="0%-100%")
        self.slider = RangeSlider(parent)

        self.name = name
        self.__click = False

        self.slider.Bind(wx.EVT_SLIDER, self.__on_slider, self.slider)
        self.display.Bind(wx.EVT_LEFT_UP, self.__check_click)
        self.display.Bind(wx.EVT_LEFT_DOWN, self.__set_click)
        self.display.Bind(wx.EVT_LEAVE_WINDOW, self.__unset_click)

        self.slider.Bind(EVT_RANGE_SLIDER, self.__on_slider)

    def __set_click(self, evt):
        self.__click = True
    def __unset_click(self, evt):
        self.__click = False
    def __check_click(self, evt):
        if self.__click:
            rsd = RangeSliderSetDialog(None, self.label.GetLabel(), self.slider.GetRange()[0], self.slider.GetRange()[1])
            rsd.ShowModal()
            r = rsd.GetRange()
            if r == None:
                wx.MessageBox("Minimum cannot be greater than maximum!", "Range Error", wx.ICON_ERROR | wx.OK)
                return
            self.slider.SetRange(r[0], r[1])
            self.__on_slider()
            self.__click = False
        
    def __on_slider(self, evt=None):
        v = self.slider.GetIntRange()
        self.display.SetLabel("%d%%-%d%%" % (v[0], v[1]))
        
    def GetRange(self):
        return self.slider.GetRange()
    def GetIntRange(self):
        return self.slider.GetIntRange()
    def SetRange(self, minimum, maximum):
        self.slider.SetRange(minimum, maximum)
        self.__on_slider()
    def GetMinimum(self):
        return self.slider.GetMinimum()
    def GetMaximum(self):
        return self.slider.GetMaximum()
        
class RangeSliderList(wx.ScrolledWindow):
    def __init__(self, parent, randomizer=False):
        wx.ScrolledWindow.__init__(self, parent, style=wx.SIMPLE_BORDER)

        self.__randomizer = randomizer

        self.__items = []
        self.__specs = []
        self.__sizer = wx.FlexGridSizer(rows=0, cols=3, hgap=0, vgap=5)

        self.SetSizer(self.__sizer)
        
        if randomizer:
            self.rand_btn = wx.Button(self, label="Randomize")
            self.rand_btn.Bind(wx.EVT_BUTTON, self.Randomizer)

            self.__sizer.Add(wx.Panel(self))
            self.__sizer.Add(self.rand_btn, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
            self.__sizer.Add(wx.Panel(self))
        else:
            self.rand_btn = None

        self.ShowScrollbars(wx.SHOW_SB_DEFAULT, wx.SHOW_SB_DEFAULT)
        self.SetScrollRate(3, 12)

        self.Bind(wx.EVT_CHILD_FOCUS, self.__focus_on_me)

    def Randomizer(self, evt):
        for i in self.__items:
            a = random.randint(i.GetMinimum(), i.GetMaximum())
            b = random.randint(i.GetMinimum(), i.GetMaximum())
            i.SetRange(min(a,b), max(a,b))

    def __focus_on_me(self, evt):
        if evt.GetEventObject() == self.rand_btn:
            return
        self.SetFocusIgnoringChildren()

    def GetSizer(self):
        return self.__sizer

    def Append(self, name, specId, label=None):
        if label == None:
            label = name
        for i in self.__items:
            if i.name == name:
                raise ValueError("Name '%s' already exists in list!" % name)
        litem = RangeSliderListItem(self, name, label)
        self.__items.append( litem )
        self.__specs.append( specId )
        
        self.__sizer.Add(litem.label, flag=wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, border=7)
        self.__sizer.Add(litem.slider, flag=wx.ALL, border=7)
        self.__sizer.Add(litem.display, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=7)
        self.__sizer.Layout()
        self.FitInside()

    def GetItemNames(self):
        return [i.name for i in self.__items]
    def GetItemIds(self):
        return self.__specs
    def HasId(self, item_id):
        return item_id in self.__specs
    def HasKey(self, name):
        return name in [i.name for i in self.__items]

    def GetRange(self, specId):
        for i in xrange(0, len(self.__items)):
            if self.__specs[i] == specId:
                return self.__items[i].GetRange()
        raise ValueError("No elemented named '%s'." % name)

    def GetIntRange(self, specId):
        for i in xrange(0, len(self.__items)):
            if self.__specs[i] == specId:
                return self.__items[i].GetIntRange()
        raise ValueError("No elemented named '%s'." % name)

    def SetRange(self, specId, minimum, maximum):
        for i in xrange(0, len(self.__items)):
            if self.__specs[i] == specId:
                return self.__items[i].SetRange(minimum, maximum)
        raise KeyError("No item '%s' found." % name)

    def Remove(self, name):
        """Remove(name) - Remove item with specified name value"""
        del_ind = -1
        comp = None
        for i in xrange(0, len(self.__items)):
            cur = self.__items[i]
            if cur.name == name:
                comp.label.Destroy()
                comp.slider.Destroy()
                comp.display.Destroy()
                del_ind = i
                comp = cur
                break

        if comp != None:
            self.__sizer.Remove(comp.label)
            self.__sizer.Remove(comp.slider)
            self.__sizer.Remove(comp.display)
            self.__sizer.Layout()
            self.FitInside()

        del comp
        
        if del_ind >= 0:
            del self.__items[del_ind]
            del self.__specs[del_ind]

    def RemoveIndex(self, index):
        comp = self.__items[index]

        comp.label.Destroy()
        comp.slider.Destroy()
        comp.display.Destroy()

        self.__sizer.Remove(comp.label)
        self.__sizer.Remove(comp.slider)
        self.__sizer.Remove(comp.display)
        self.__sizer.Layout()
        self.FitInside()

        del comp
        del self.__items[del_ind]
        del self.__specs[del_ind]

    def Reset(self):
        for i in self.__items:
            i.SetRange(i.GetMinimum(), i.GetMaximum())

    def Clear(self):
        del self.__items
        del self.__specs
        self.__items = []
        self.__specs = []

        self.__sizer.Clear(True)

        if self.__randomizer:
            self.rand_btn = wx.Button(self, label="Randomize")
            self.rand_btn.Bind(wx.EVT_BUTTON, self.Randomizer)

            self.__sizer.Add(wx.Panel(self))
            self.__sizer.Add(self.rand_btn, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
            self.__sizer.Add(wx.Panel(self))

        self.__sizer.Layout()
        
        self.FitInside()
