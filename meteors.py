import random
import math
import pyglet
from pyglet.gl import *
from pyglet.window import key

# float comparison courtesy of stack overflow
# http://stackoverflow.com/questions/10334688/how-dangerous-is-it-to-compare-floating-point-values
FL_EPS = 0.0000001192092896
FL_MIN = 1.175494e-38
def near(f1, f2, k = 1):
    return (abs(f1 - f2) < k * FL_EPS * abs(f1 + f2) or abs(f1 - f2) < FL_MIN)

# enums courtesy of stackoverflow
# http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
# modified to skip 0 (to avoid being evaluated as false)
def enum(*sequential, **named):
    enums = dict(zip(sequential, range(1, len(sequential) + 1)), **named)
    return type('Enum', (), enums)

# some global enumerations to avoid typos/comparing strings
TURN = enum('left', 'right')
THRUST = enum('forward', 'back')
STATE = enum('start', 'play', 'game_over', 'level')

class Vector2():
    # 2D vector/point
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def copy(self):
        return Vector2(self.x, self.y)

    def __abs__(self): # gives the value squared to avoid sqrt
        return (self.x * self.x + self.y * self.y)

    def __add__(self, v2):
        return Vector2(self.x + v2.x, self.y + v2.y)

    def __sub__(self, v2):
        return Vector2(self.x - v2.x, self.y - v2.y)

    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)

    def __div__(self, scalar):
        return Vector2(self.x / scalar, self.y / scalar)

    def update(self, v2):
        # use this instead of assignment to update a vector in place
        self.x = v2.x
        self.y = v2.y

    def slope(self):
        # returns None if infinite
        if self.x == 0:
            return None
        else:
            return (self.y / self.x)

    def cross(self, v2):
        return (self.x * v2.y - self.y * v2.x)

    def normalize(self):
        denom = math.sqrt(abs(self))
        return Vector2(self.x / denom, self.y / denom)


class Line():
    # line segment helper. start and end are Vector2
    def __init__(self, start, end):
        # if the two points are actually exactly same (happens very rarely, only on 0,0),
        # then fake a short line so it still responds to intersection
        if start.y == end.y and start.x == end.x:
            start.y = start.y + 0.1
            start.x = start.x + 0.1
        self.start = start
        self.end = end

    def slope(self):
        # returns None if infinite
        return (self.end - self.start).slope()

    def offset(self):
        # returns None if slope is infinite
        if self.slope():
            return (self.start.y - self.slope() * self.start.x)
        else:
            return None

    def get_abc(self):
        # returns A, B, C that define the line as Ax + By = C
        a = self.end.y - self.start.y
        b = self.start.x - self.end.x
        c = a * self.start.x + b * self.start.y
        return [a, b, c]

    def within(self, point):
        # returns true if the point lies within the box formed by the start and end points
        if near(self.start.x, self.end.x):
            c1 = near(point.x, self.start.x)
        else:
            c1 = point.x < max(self.start.x, self.end.x) and point.x > min(self.start.x, self.end.x)
        if near(self.start.y, self.end.y):
            c2 = near(point.y, self.start.y)
        else:
            c2 = point.y < max(self.start.y, self.end.y) and point.y > min(self.start.y, self.end.y)
        return c1 and c2

    def intersection(self, line):
        # returns the point of intersection if the lines were infinite.
        # if parallel, will return None
        (a1, b1, c1) = self.get_abc()
        (a2, b2, c2) = line.get_abc()
        det = a1 * b2 - a2 * b1
        if det == 0:
            return None
        else:
            x = float(b2 * c1 - b1 * c2) / det
            y = float(a1 * c2 - a2 * c1) / det
            return Vector2(x, y)

    def intersect(self, line):
        # returns true if the line segments intersect
        point = self.intersection(line)
        if point:
            return self.within(point) and line.within(point)
        else:
            return False


class BoundingCircle():
    # bounding circle helper
    def __init__(self, center, radius):
        self.center = center
        self.radius = radius

    def inside(self, point):
        # returns true if the point is inside the circle
        return abs(point - self.center) < (self.radius * self.radius)


class WObject():
    # Represents a game/world object. Handles it's own rendering, and updating.
    # Game objects should subclass this one. Contains some helper functions as well.
    def __init__(self):
        # how many past pos/deg to keep track of
        self.state_buffer = 5 
        # position (x,y) (x > 0 => right, y > 0 => up)
        self.init_pos(Vector2(0, 0))
        # angular position in degrees. 0 = up, 90 = left
        self.init_deg(0)
        # velocity vector
        self.vel = Vector2(0, 0)
        # size vector
        self.size = Vector2(1, 1)
        # flag to mark object for removal
        self.remove = False
        
        # Define the shape. Place all vertexes within the unit square as defined below.
        #  Use size to then size it appropriately. Points should always be in groups of
        #  2 vectors. To connect lines, you must define the connecting
        #  vertices twice.
        self.points = self.to_points([0, 0, 0, 1, 
                                      0, 1, 1, 1, 
                                      1, 1, 1, 0, 
                                      1, 0, 0, 0]) # square

        # where within the unit square should the position be defined.
        # it is also the point about which the object will rotate
        self.anchor = Vector2(0.5, 0.5)
        
        # color in RGB
        self.color = [1, 1, 1]

        # debug stuff
        self.box = self.points 
        self.circle = self.generate_circle(48)
        self.cross = self.to_points([0, 0.5, 1, 0.5, 0.5, 0, 0.5, 1])
        self.draw_box = False # shows the unit box around the object
        self.draw_circle = False # shows the unit circle around the object
        self.draw_cross = False # shows a unit cross centered on object
        self.draw_transform = False # draw the points transformed in cpu space
        self.draw_pos_change = False # draws the positional change between two frames as a line

    def to_points(self, p_list):
        # converts flat list of floats to list of Vector2
        points = []
        for i in range(len(p_list) / 2):
            x = p_list[i * 2]
            y = p_list[i * 2 + 1]
            points.append(Vector2(x, y))
        return points

    def get_point_transformed(self, index, num = 0):
        # returns the point at index from by self.points but after
        #  translation/rotation/scaling via cpu. 
        # if num > 0, will return the points generated from an older state
        num = num % self.state_buffer
        point = self.points[index]
        # center on anchor
        point = point - self.anchor
        # scale
        point.x = point.x * self.size.x
        point.y = point.y * self.size.y
        # rotate
        if num > 0:
            deg = self.last_deg[num - 1]
        else:
            deg = self.deg
        sin = math.sin(math.radians(deg))
        cos = math.cos(math.radians(deg))
        x = point.x * cos - point.y * sin
        y = point.x * sin + point.y * cos
        point.y = y
        point.x = x
        # translate
        if num > 0:
            pos = self.last_pos[num - 1]
        else:
            pos = self.pos
        point = point + pos
        return point

    def get_all_points_transformed(self, num = 0):
        # returns all transformed points. maybe slow for many points
        points = []
        for i in range(len(self.points)):
            points.append(self.get_point_transformed(i, num))
        return points

    def get_lines(self):
        # returns a list of all line segments defined by points after transformation.
        lines = []
        for i in range(len(self.points) / 2):
            p1 = self.get_point_transformed(i * 2)
            p2 = self.get_point_transformed(i * 2 + 1)
            lines.append(Line(p1, p2))
        return lines

    def init_pos(self, pos):
        # initialize position vector
        self.pos = pos
        self.last_pos = []
        for i in range(self.state_buffer):
            self.last_pos.append(pos)

    def update_pos(self, pos):
        # update the position vector
        self.last_pos.insert(0, self.pos)
        self.last_pos.pop()
        self.pos = pos

    def init_deg(self, deg):
        # initialize degrees member
        self.deg = deg
        self.last_deg = []
        for i in range(self.state_buffer):
            self.last_deg.append(deg)

    def update_deg(self, deg):
        # update the degrees member
        self.last_deg.insert(0, self.deg)
        self.last_deg.pop()
        self.deg = deg

    def get_pos_change(self, num):
        # the positional change from num update cycles ago (where num < self.state_buffer)
        num = num % self.state_buffer
        return self.pos - self.last_pos[num]

    def generate_circle(self, num_points):
        # generates a unit circle with num_points
        interval = 360.0 / num_points
        points = []
        first = None
        for i in range(num_points + 1):
            deg = i * interval
            p = self.deg_to_vel(deg) / 2 + Vector2(0.5, 0.5)
            points.append(p)
            if i == 0:
                first = p
            else:
                points.append(p)
        points.append(first)
        return points

    def deg_to_vel(self, deg):
        # convert degrees (up => 0, left => 90) 
        #  to a normalized vector (top|right => y|x > 0)
        y = abs(math.tan(math.radians(deg-90)))
        x = 1
        if deg > 0 and deg < 180:
            x = -1
        if deg > 90 and deg < 270:
            y = -y
        return Vector2(x, y).normalize()

    def draw_points(self, points):
        # draws the set of point pairs as GL_LINES
        the_points = []
        for point in points:
            the_points.append(point.x)
            the_points.append(point.y)
        pyglet.graphics.draw(len(points), GL_LINES, ('v2f', the_points))

    def draw(self):
        # simple scale/rotate/tranlate and color of gl lines
        glLoadIdentity()
        if self.draw_pos_change:
            glColor3f(1, 1, 0)
            points = [self.last_pos.x, self.last_pos.y, self.pos.x, self.pos.y]
            self.draw_points(points)
        if self.draw_transform:
            points = self.get_all_points_transformed()
            glColor3f(0, 0, 1)
            self.draw_points(points)
        glColor3f(self.color[0], self.color[1], self.color[2])
        glTranslatef(self.pos.x, self.pos.y, 0)
        glRotatef(self.deg, 0, 0, 1)
        glScalef(self.size.x, self.size.y, 1)
        glTranslatef(-self.anchor.x, -self.anchor.y, 0)
        self.draw_points(self.points)
        if self.draw_box:
            self.draw_points(self.box)
        if self.draw_circle:
            self.draw_points(self.circle)
        if self.draw_cross:
            self.draw_points(self.cross)


class Font(WObject):
    # drawable text object
    def __init__(self, pos, size, opts = {}):
        WObject.__init__(self)
        self.anchor = Vector2(0, 0)
        self.pos = pos
        self.size = size
        self.opts = {
            'spacing' : 0.2,        # space between characters relative to width
            'just-y'  : 'bottom',   # vertical justification (top|bottom|center)
            'just-x'  : 'left'      # horizontal justification (left|right|center)
        }
        self.opts.update(opts)
        self.string = ""
        self.did_update_string = True
        self._init_char_points()

    def set_string(self, string):
        # set the string to display
        self.string = string
        self.did_update_string = True

    def update(self, time, window):
        if self.did_update_string:
            self.did_update_string = False
            self.points = self._string_to_points(self.string)

    def _string_to_points(self, string):
        points = []
        index = 0
        for char in string:
            points = points + self._char_to_points(char, index)
            index += 1
        return points

    def _char_to_points(self, char, index):
        if char in self.char_points:
            points = self.to_points(self.char_points[char])
        else:
            points = []
        extra = self._find_extra(index)
        for point in points:
            point.update(point + extra)
        return points

    def _find_extra(self, index):
        extra = Vector2(0, 0)
        extra.x = (1 + self.opts['spacing']) * index
        if self.opts['just-x'] == 'center':
            extra.x = extra.x - self._find_width() / 2
        if self.opts['just-x'] == 'right':
            extra.x = extra.x - self._find_width()
        if self.opts['just-y'] == 'center':
            extra.y = extra.y - self._find_height() / 2
        if self.opts['just-y'] == 'top':
            extra.y = extra.y - self._find_height()
        return extra

    def _find_width(self):
        length = len(self.string)
        return length + self.opts['spacing'] * (length - 1)

    def _find_height(self):
        return 1

    def _init_char_points(self):
        # oh god why
        self.char_points = {
            'A': [0, 0, 0.5, 1, 0.5, 1, 1, 0, 0.25, 0.5, 0.75, 0.5],
            'B': [0, 0, 0, 1, 0, 1, 0.75, 1, 0.75, 1, 1, 0.75, 1, 0.75, 0.75, 0.5, 0.75, 
                    0.5, 1, 0.25, 1, 0.25, 0.75, 0, 0.75, 0, 0, 0, 0, 0.5, 0.75, 0.5],
            'C': [1, 0.25, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 0, 0, 0.25, 0, 0.25, 0, 
                    0.75, 0, 0.75, 0.25, 1, 0.25, 1, 0.75, 1, 0.75, 1, 1, 0.75],
            'D': [0, 0, 0, 1, 0, 1, 0.75, 1, 0.75, 1, 1, 0.75, 1, 0.75, 1, 0.25, 
                    1, 0.25, 0.75, 0, 0.75, 0, 0, 0],
            'E': [0, 1, 1, 1, 0, 0.5, 0.75, 0.5, 0, 0, 1, 0, 0, 0, 0, 1],
            'F': [0, 0, 0, 1, 0, 1, 1, 1, 0, 0.5, 0.75, 0.5],
            'G': [1, 0.75, 0.75, 1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 
                    0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 1, 0.5, 1, 0.5, 0.5, 0.5],
            'H': [0, 0, 0, 1, 1, 0, 1, 1, 0, 0.5, 1, 0.5],
            'I': [0.25, 1, 0.75, 1, 0.25, 0, 0.75, 0, 0.5, 0, 0.5, 1],
            'J': [0, 0, 0.5, 0, 0.5, 0, 0.5, 1, 0, 1, 1, 1],
            'K': [0, 0, 0, 1, 0, 0.5, 1, 1, 0, 0.5, 1, 0],
            'L': [0, 0, 0, 1, 0, 0, 1, 0],
            'M': [0, 0, 0, 1, 0, 1, 0.5, 0.5, 0.5, 0.5, 1, 1, 1, 1, 1, 0],
            'N': [0, 0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1],
            'O': [1, 0.75, 0.75, 1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 
                    0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 1, 0.75],
            'P': [0, 0, 0, 1, 0, 1, 0.75, 1, 0.75, 1, 1, 0.75, 1, 0.75, 0.75, 0.5, 0.75, 0.5, 0, 0.5],
            'Q': [1, 0.75, 0.75, 1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 
                    0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 1, 0.75, 0.75, 0.25, 1, 0],
            'R': [0, 0, 0, 1, 0, 1, 0.75, 1, 0.75, 1, 1, 0.75, 1, 0.75, 0.75, 0.5, 
                    0.75, 0.5, 0, 0.5, 0.75, 0.5, 1, 0],
            'S': [0, 0.25, 0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 0.75, 0.5, 0.75, 0.5, 
                    0.25, 0.5, 0.25, 0.5, 0, 0.75, 0, 0.75, 0.25, 1, 0.25, 1, 0.75, 1, 0.75, 1, 1, 0.75],
            'T': [0, 1, 1, 1, 0.5, 1, 0.5, 0],
            'U': [0, 1, 0, 0.25, 0, 0.25, 0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 1, 1],
            'V': [0, 1, 0.5, 0, 0.5, 0, 1, 1],
            'W': [0, 1, 0, 0, 0, 0, 0.5, 0.5, 0.5, 0.5, 1, 0, 1, 0, 1, 1],
            'X': [0, 0, 1, 1, 1, 0, 0, 1],
            'Y': [0, 1, 0.5, 0.5, 0.5, 0.5, 1, 1, 0.5, 0.5, 0.5, 0],
            'Z': [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0],
            '1': [0, 0.75, 0.5, 1, 0.5, 1, 0.5, 0, 0, 0, 1, 0],
            '2': [1, 0, 0, 0, 0, 0, 0.75, 0.5, 0.75, 0.5, 1, 0.75, 1, 0.75, 0.75, 
                    1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75],
            '3': [0, 0.75, 0.25, 1, 0.25, 1, 0.75, 1, 0.75, 1, 1, 0.75, 1, 0.75, 0.75, 0.5, 0.75, 
                    0.5, 1, 0.25, 1, 0.25, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 0, 0, 0.25, 0.25, 0.5, 0.75, 0.5],
            '4': [0.75, 0, 0.75, 1, 0.75, 1, 0, 0.25, 0, 0.25, 1, 0.25],
            '5': [1, 1, 0, 1, 0, 1, 0, 0.5, 0, 0.5, 0.75, 0.5, 0.75, 0.5, 1, 0.25, 
                    1, 0.25, 0.75, 0, 0.75, 0, 0, 0],
            '6': [1, 0.75, 0.75, 1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 0.25, 
                    0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 0.75, 0.5, 0.75, 0.5, 0, 0.5],
            '7': [0, 1, 1, 1, 1, 1, 0.25, 0],
            '8': [0, 0.75, 0.25, 1, 0.25, 1, 0.75, 1, 0.75, 1, 1, 0.75, 1, 0.75, 0.75, 0.5, 0.75, 
                    0.5, 1, 0.25, 1, 0.25, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 0, 0, 0.25, 
                    0, 0.25, 0.25, 0.5, 0.25, 0.5, 0, 0.75, 0.25, 0.5, 0.75, 0.5],
            '9': [0, 0.25, 0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 1, 0.75, 1, 0.75, 
                    0.75, 1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75, 0, 0.75, 0.25, 0.5, 0.25, 0.5, 1, 0.5],
            '0': [1, 0.75, 0.75, 1, 0.75, 1, 0.25, 1, 0.25, 1, 0, 0.75, 0, 0.75, 0, 0.25, 0, 0.25, 
                    0.25, 0, 0.25, 0, 0.75, 0, 0.75, 0, 1, 0.25, 1, 0.25, 1, 0.75, 0.75, 1, 0.25, 0],
        }


class Meteor(WObject):
    # Meteor bass class
    def __init__(self, start_pos, start_deg, num_points, size, speed, max_health):
        WObject.__init__(self)
        self.init_pos(start_pos)
        self.vel = self.deg_to_vel(start_deg) * speed
        self.size = Vector2(size, size)
        self.num_points = num_points
        self.points = self.generate_points()
        self.turn_speed = random.uniform(-20, 20)

        self.max_health = max_health
        self.health = self.max_health

        self.draw_circle = False

    def bounding_circle(self):
        return BoundingCircle(self.pos, self.size.x / 2)

    def hit(self):
        self.health = self.health - 1
        if self.health == 0:
            self.remove = True

    def generate_points(self):
        interval = 360 / self.num_points
        points = []
        first = None
        for i in range(self.num_points):
            deg = i * interval
            length = random.uniform(0.7, 1) / 2
            p = self.deg_to_vel(deg) * length + Vector2(0.5, 0.5)
            points.append(p)
            if i == 0:
                first = p
            else:
                points.append(p)
        points.append(first)
        return points

    def update(self, time, window):
        # update color (white -> yellow -> red)
        # bias to make 1 health completely red and full health completely white
        # max_health must be greater than 1
        h = float(self.health - 1) / (self.max_health - 1)
        if h > 0.5: # approach yellow
            self.color = [1, 1, (h - 0.5) / 0.5]
        else: # approach red
            self.color = [1, h / 0.5, 0]
       
        # rotate
        self.update_deg(self.deg + self.turn_speed * time)

        # update position
        # allow to dissappear off edge, but jump to the opposite edge once that happens
        pos = self.pos + self.vel * time
        (winx, winy) = window.get_size()
        if pos.x < 0 - self.size.x / 2:
            pos.x = pos.x + (1.5 * self.size.x + winx)
        if pos.x > winx + self.size.x:
            pos.x = pos.x - (1.5 * self.size.x + winx)
        if pos.y < 0 - self.size.y:
            pos.y = pos.y + (1.5 * self.size.y + winy)
        if pos.y > winy + self.size.y:
            pos.y = pos.y - (1.5 * self.size.y + winy)
        self.update_pos(pos)


class Meteor1(Meteor):
    # big meteor
    def __init__(self, start_pos, start_deg):
        Meteor.__init__(self, start_pos, start_deg, 18, 200, 40, 6)


class Meteor2(Meteor):
    # medium meteor
    def __init__(self, start_pos, start_deg):
        Meteor.__init__(self, start_pos, start_deg, 12, 100, 60, 4)


class Meteor3(Meteor):
    # small meteor
    def __init__(self, start_pos, start_deg):
        Meteor.__init__(self, start_pos, start_deg, 8, 40, 80, 2)


class Bullet(WObject):
    # gun projectile
    def __init__(self, start_pos, start_deg):
        WObject.__init__(self)
        self.init_pos(start_pos)
        self.vel = self.deg_to_vel(start_deg) * 500
        self.init_deg(start_deg)
        self.size = Vector2(5, 9)
        self.points = self.to_points([0, 0, 0.5, 1, 0.5, 1, 1, 0, 1, 0, 0, 0])

    def update(self, time, window):
        # update position and flag for removal if off screen
        self.update_pos(self.pos + self.vel * time)
        (winx, winy) = window.get_size()
        if self.pos.x < 0 or self.pos.x > winx or self.pos.y < 0 or self.pos.y > winy:
            self.remove = True

    def hit(self):
        self.remove = True

class Ship(WObject):
    # the players ship
    def __init__(self, start_pos):
        WObject.__init__(self)
        self.init_pos(start_pos)
        self.size = Vector2(20, 40)
        self.init_deg(0)
        self.vel = Vector2(0, 0)

        self.accel = 300
        self.turn_speed = 200
        self.turn_state = None
        self.thrust_state = None

        self.points = self.to_points([0.5, 1, 1, 0, 
                                      1, 0, 0.5, 0.2, 
                                      0.5, 0.2, 0, 0, 
                                      0, 0, 0.5, 1])

    def hit(self):
        self.remove = True

    def turn(self, direction, press):
        if press:
            self.turn_state = direction
        else:
            self.turn_state = None

    def thrust(self, direction, press):
        if press:
            self.thrust_state = direction
        else:
            self.thrust_state = None

    def update(self, time, window):
        # update velocity
        if self.thrust_state:
            added_vel = self.deg_to_vel(self.deg) * self.accel * time
            if self.thrust_state == THRUST.forward:
                self.vel = self.vel + added_vel
            elif self.thrust_state == THRUST.back:
                self.vel = self.vel - added_vel

        # update angle
        if self.turn_state:
            if self.turn_state == TURN.left:
                self.update_deg(self.deg + self.turn_speed * time)
            elif self.turn_state == TURN.right:
                self.update_deg(self.deg - self.turn_speed * time)
            self.update_deg(self.deg % 360)
       
        # update position based on velocity and keep within window
        pos = self.pos + self.vel * time
        (winx, winy) = window.get_size()
        pos.x = pos.x % winx
        pos.y = pos.y % winy
        self.update_pos(pos)


class Collider():
    # Helper class to aid with collision detection.
    # Register collision detection and handling methods for particular pairs of
    # objects (by class name), and you can then just call Collider.collide(obj1, obj2),
    # and Collider.handle(obj1, obj2) and this class will call the appropriate methods.
    def __init__(self):
        self.method_dict = dict()

    def register_methods(self, detector, handler, type1, type2):
        # Pass in a collision detection method, a collision handling method,
        #  and two object class names as strings.
        # The methods are expected to accept two arguments (the two objects)
        #  in the order which their types are submitted. Will raise an error if you register
        #  a method for the same pair of objects
        if self._find_methods(type1, type2) != None or self._find_methods(type2, type1) != None:
            raise('Already registered methods for ' + type1 + ' and ' + type2)
        if not type1 in self.method_dict:
            self.method_dict[type1] = dict()
        self.method_dict[type1][type2] = [detector, handler]

    def collide(self, obj1, obj2):
        # Pass it any two world objects (in any order) and it will call the appropriate
        #   collision detection method (based on their type) and return true if they collided.
        # If there is no method registered for that pair, it will return false.
        if obj1.remove or obj2.remove:
            return False
        type1 = self._type(obj1)
        type2 = self._type(obj2)
        methods1 = self._find_methods(type1, type2)
        methods2 = self._find_methods(type2, type1)
        if methods1 == None and methods2 == None:
            return False
        # only one of these will do something
        if methods1 != None:
            return methods1[0](obj1, obj2)
        elif methods2 != None:
            return methods2[0](obj2, obj1)
        return False

    def handle(self, obj1, obj2):
        # Pass it any two world objects (in any order) and it will call the appropriate
        #   collision handling method (based on their type).
        # If there is no method registered for that pair, it will do nothing.
        if obj1.remove or obj2.remove:
            return
        type1 = self._type(obj1)
        type2 = self._type(obj2)
        methods1 = self._find_methods(type1, type2)
        methods2 = self._find_methods(type2, type1)
        if methods1 == None and methods2 == None:
            return
        # only one of these will do something
        if methods1 != None:
            methods1[1](obj1, obj2)
        elif methods2 != None:
            methods2[1](obj2, obj1)

    def _find_methods(self, type1, type2):
        if type1 in self.method_dict:
            if type2 in self.method_dict[type1]:
                return self.method_dict[type1][type2]
        return None

    def _type(self, obj):
        return obj.__class__.__name__


class Game():
    # game logic/event handling class
    def __init__(self, window):
        self._init_window(window)
        self._init_opengl()
        self._init_collider()
        
        # list to hold all game objects
        self.items = []

        # set the initial score and level
        self.score = 0
        self.level = 1

        # set the initial state (start screen)
        self._init_start()

    # misc initializers

    def _init_window(self, window):
        self.window = window
        self.window.clear()
        self.window.flip()
        self.window.set_visible(True)

    def _init_opengl(self):
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        self._aa = True

    def _toggle_aa(self):
        if self._aa:
            glDisable(GL_LINE_SMOOTH)
            glDisable(GL_BLEND)
            self._aa = False
        else:
            glEnable(GL_BLEND)
            glEnable(GL_LINE_SMOOTH)
            self._aa = True

    def _init_collider(self):
        self.collider = Collider()
        self.collider.register_methods(
            self._cd_ship_meteor,
            self._ch_ship_meteor,
            'Ship', 'Meteor1')
        self.collider.register_methods(
            self._cd_ship_meteor,
            self._ch_ship_meteor,
            'Ship', 'Meteor2')
        self.collider.register_methods(
            self._cd_ship_meteor,
            self._ch_ship_meteor,
            'Ship', 'Meteor3')
        self.collider.register_methods(
            self._cd_bullet_meteor,
            self._ch_bullet_meteor1,
            'Bullet', 'Meteor1')
        self.collider.register_methods(
            self._cd_bullet_meteor,
            self._ch_bullet_meteor2,
            'Bullet', 'Meteor2')
        self.collider.register_methods(
            self._cd_bullet_meteor,
            self._ch_bullet_meteor3,
            'Bullet', 'Meteor3')

    # state initializers
    
    def _init_start(self):
        # initialize the start screen
        self.state = STATE.start
        self.remove_all_items()
        (winx, winy) = self.window.get_size()
        s1 = Font(
            Vector2(winx / 2, winy / 2), 
            Vector2(20, 30), 
            {'just-x' : 'center',
             'just-y' : 'center'})
        s1.set_string('PRESS ENTER TO START')
        s1.color = [0.5, 0.5, 1]
        self.add_item(s1)
        s2 = Font(
            Vector2(winx / 2, winy / 2 - 40), 
            Vector2(10, 15), 
            {'just-x' : 'center',
             'just-y' : 'center',
             'spacing': 0.3})
        s2.set_string('ARROW KEYS TO MOVE')
        s2.color = [0.7, 0.7, 0.7]
        self.add_item(s2)
        s2 = Font(
            Vector2(winx / 2, winy / 2 - 63), 
            Vector2(10, 15), 
            {'just-x' : 'center',
             'just-y' : 'center',
             'spacing': 0.3})
        s2.set_string('SPACE OR S TO SHOOT')
        s2.color = [0.7, 0.7, 0.7]
        self.add_item(s2)

    def _init_level(self):
        # initialize the level transition screen
        self.level = self.level + 1
        self.state = STATE.level
        self.remove_all_items()
        (winx, winy) = self.window.get_size()
        s = Font(
            Vector2(winx / 2, winy / 2), 
            Vector2(20, 30), 
            {'just-x' : 'center',
             'just-y' : 'center'})
        s.set_string('LEVEL %d' % self.level)
        s.color = [0.5, 0.5, 1]
        self.add_item(s)

    def _init_play(self):
        # initialize the game
        self.remove_all_items()
        self.meteors = []
        self.bullet = None
        (winx, winy) = self.window.get_size()
        self.score_text = Font(
            Vector2(5, winy - 5), 
            Vector2(10, 15), 
            {'just-x' : 'left',
             'just-y' : 'top'})
        self.add_item(self.score_text)
        self.add_to_score(0)
        self.state = STATE.play
        self.add_ship()
        self.add_meteor1()

    def _init_game_over(self):
        # initialize the game over screen
        self.level = 1
        self.score = 0
        self.remove_all_items()
        self.state = STATE.game_over
        (winx, winy) = self.window.get_size()
        s = Font(
            Vector2(winx / 2, winy / 2), 
            Vector2(20, 30), 
            {'just-x' : 'center',
             'just-y' : 'center'})
        s.set_string('YOU DIED')
        s.color = [1, 0, 0]
        self.add_item(s)
        self.add_item(self.score_text)

    # helpers

    def add_item(self, item):
        self.items.append(item)

    def remove_item(self, item):
        self.items.remove(item)
        if item == self.bullet:
            self.bullet = None

    def remove_all_items(self):
        self.items = []

    def add_to_score(self, num):
        self.score = self.score + num * self.level
        self.score_text.set_string("SCORE %d" % self.score)

    # game object initializers

    def add_ship(self):
        (winx, winy) = self.window.get_size()
        pos = Vector2(winx / 2, winy / 2)
        self.ship = Ship(pos)
        self.add_item(self.ship)

    def add_bullet(self):
        if self.bullet == None:
            pos = self.ship.pos + self.ship.deg_to_vel(self.ship.deg) * self.ship.size.y / 2
            self.bullet = Bullet(pos, self.ship.deg)
            self.add_item(self.bullet)

    def add_meteor1(self):
        # adds large meteors in random locations, with random directions.
        # makes sure it's far enough away from the ship, and from each other
        (winx, winy) = self.window.get_size()
        count = self.level
        last_poses = []
        for i in range(count):
            search = True
            while search:
                pos = Vector2(random.uniform(0, winx), random.uniform(0, winy))
                search = False
                for last_pos in last_poses:
                    if abs(pos - last_pos) < 20000:
                        search = True
                        break 
                if abs(pos - self.ship.pos) < 20000:
                    search = True
            last_poses.append(pos)
            deg = random.uniform(0, 360)
            m = Meteor1(pos, deg)
            self.add_item(m)
            self.meteors.append(m)

    def add_meteor2(self, pos):
        # adds meteor2s where a meteor1 was exploded (pos)
        # uses random directions, but at least 0.2 * (360/count) degrees apart
        count = 3
        min_separation = 0.2 * (360 / count)
        last_degs = []
        for i in range(count):
            search = True
            while search:
                deg = random.uniform(0, 360)
                search = False
                for last_deg in last_degs:
                    if abs(deg - last_deg) < min_separation:
                        search = True
                        break
            last_degs.append(deg)
            m = Meteor2(pos, deg)
            self.add_item(m)
            self.meteors.append(m)

    def add_meteor3(self, pos):
        # adds meteor2s where an meteor1 was exploded (pos)
        # uses random directions, but at least 0.2 * (360/count) degrees apart
        count = 3
        min_separation = 0.2 * (360 / count)
        last_degs = []
        for i in range(count):
            search = True
            while search:
                deg = random.uniform(0, 360)
                search = False
                for last_deg in last_degs:
                    if abs(deg - last_deg) < min_separation:
                        search = True
                        break
            last_degs.append(deg)
            m = Meteor3(pos, deg)
            self.add_item(m)
            self.meteors.append(m)

    # keyboard event handler

    def on_key(self, symbol, modifiers, press):
        if symbol == key.ENTER and press:
            if self.state == STATE.start:
                self._init_play()
            elif self.state == STATE.game_over:
                self._init_start()
            elif self.state == STATE.level:
                self._init_play()
        elif symbol == key.RIGHT:
            if self.state == STATE.play:
                self.ship.turn(TURN.right, press) 
        elif symbol == key.LEFT:
            if self.state == STATE.play:
                self.ship.turn(TURN.left, press) 
        elif symbol == key.UP:
            if self.state == STATE.play:
                self.ship.thrust(THRUST.forward, press) 
        elif symbol == key.DOWN:
            if self.state == STATE.play:
                self.ship.thrust(THRUST.back, press)
        elif (symbol == key.SPACE or symbol == key.S) and press:
            if self.state == STATE.play:
                self.add_bullet()
        elif symbol == key.A and press:
            self._toggle_aa()

    # render event handler

    def draw(self):
        self.window.clear()
        for item in self.items:
            item.draw()

    # update event handler

    def update(self, frame_time):
        # update game objects
        for item in self.items:
            if item.remove:
                self.remove_item(item)
                if item == self.ship:
                    self._init_game_over()
            else:
                item.update(frame_time, self.window)
        # check for collisions
        if self.state == STATE.play:
            for item1 in self.items:
                for item2 in self.items:
                    if item1 != item2:
                        if self.collider.collide(item1, item2):
                            self.collider.handle(item1, item2)

    # collision detection methods (these could live anywhere really since they are purely functional)

    def _cd_ship_meteor(self, ship, meteor):
        ship_points = ship.get_all_points_transformed()
        for ship_point_index in range(len(ship_points)):
            ship_point = ship_points[ship_point_index]
            if meteor.bounding_circle().inside(ship_point):
                ship_point_old = ship.get_point_transformed(ship_point_index, 2)
                line1 = Line(ship_point_old, ship_point)
                for line2 in meteor.get_lines():
                    if line2.intersect(line1):
                        return True
        return False

    def _cd_bullet_meteor(self, bullet, meteor):
        if meteor.bounding_circle().inside(bullet.pos):
            line1 = Line(bullet.last_pos[1], bullet.pos)
            for line2 in meteor.get_lines():
                if line1.intersect(line2):
                    return True
        return False

    # collision handling methods (these have to be here since they affect the game state)

    def _ch_ship_meteor(self, ship, meteor):
        ship.hit()

    def _ch_bullet_meteor1(self, bullet, meteor):
        meteor.hit()
        bullet.hit()
        if meteor.remove:
            self.meteors.remove(meteor)
            self.add_to_score(25)
            self.add_meteor2(meteor.pos)

    def _ch_bullet_meteor2(self, bullet, meteor):
        meteor.hit()
        bullet.hit()
        if meteor.remove:
            self.meteors.remove(meteor)
            self.add_to_score(50)
            self.add_meteor3(meteor.pos)

    def _ch_bullet_meteor3(self, bullet, meteor):
        meteor.hit()
        bullet.hit()
        if meteor.remove:
            self.meteors.remove(meteor)
            self.add_to_score(100)
            if len(self.meteors) == 0:
                self._init_level()


window = pyglet.window.Window()
game = Game(window)

# Event registration
@window.event
def on_draw():
    game.draw()

@window.event
def on_key_press(symbol, modifiers):
    game.on_key(symbol, modifiers, True)

@window.event
def on_key_release(symbol, modifiers):
    game.on_key(symbol, modifiers, False)

# Register update method @ 60 fps
pyglet.clock.schedule_interval(game.update, 1.0/60.0)

# start the application
pyglet.app.run()
