import math

class LayoutGenerator:
    def __init__(self, **kwargs):
        self.bottom = kwargs.get('bottom', 0)
        self.top = kwargs.get('top', 0)
        self.left = kwargs.get('left', 0)
        self.right = kwargs.get('right', 0)

    def AdjustBounds(self, x, y):
        if self.bottom == None:
            self.bottom = y
        else:
            self.bottom = min(self.bottom, y)
            
        if self.top == None:
            self.top = y
        else:
            self.top = max(self.top, y)

        if self.left == None:
            self.left = x
        else:
            self.left = min(self.left, x)
            
        if self.right == None:
            self.right = x
        else:
            self.right = max(self.right, x)

    def GetLeft(self):
        return self.left
    def GetRight(self):
        return self.right
    def GetBottom(self):
        return self.bottom
    def GetTop(self):
        return self.top

class SpiralGenerator(LayoutGenerator):
    def __init__(self, k = 2, dtheta = math.pi / 8):
        LayoutGenerator.__init__(self)
        
        self.theta = 0
        self.dtheta = dtheta
        self.k = k

    def __iter__(self):
        return self

    def next(self):
        rval = self.k * self.theta
        
        x = rval * math.cos(self.theta)
        y = rval * math.sin(self.theta)

        self.AdjustBounds(x, y)

        self.theta += self.dtheta

        return (x, y)

class ConcentricCircleGenerator(LayoutGenerator):
    def __init__(self, rspace = 1):
        LayoutGenerator.__init__(self)
        
        self.layer = 1
        self.in_layer = 0
        self.rspace = rspace

    def __iter__(self):
        return self

    def next(self):
        theta = ((2*math.pi) / (self.layer**2)) * self.in_layer

        x = (self.rspace * (self.layer-1)) * math.cos(theta)
        y = (self.rspace * (self.layer-1)) * math.sin(theta)
        
        self.in_layer += 1
        if self.in_layer == (self.layer ** 2):
            self.layer += 1
            self.in_layer = 0

        self.AdjustBounds(x, y)

        return (x, y)
