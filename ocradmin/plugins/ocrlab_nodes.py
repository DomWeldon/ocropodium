"""
Experimental segmentation nodes.
"""

from nodetree import node, writable_node, manager
from ocradmin.plugins import stages, generic_nodes
import ocrolib
from ocrolib import iulib, numpy

NAME = "Ocrlab"

class Rectangle(object):
    """
    Rectangle class, Iulib-style.
    """
    def __init__(self, x0, y0, x1, y1):
        """
        Initialise a rectangle.
        """
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def __repr__(self):
        return "<Rectangle: %d %d %d %d>" % (
                self.x0,
                self.y0,
                self.x1,
                self.y1
        )

    def __eq__(self, rect):
        return self.x0 == rect.x0 and self.y0 == rect.y0 \
                and self.x1 == rect.x1 and self.y1 == rect.y1

    def __ne__(self, rect):
        return self.x0 != rect.x0 or self.y0 != rect.y0 \
                or self.x1 != rect.x1 or self.y1 != rect.y1

    def aspect(self):
        if self.empty():
            return 1
        return float(self.width()) / float(self.height())

    def area(self):
        if self.empty():
            return 0
        return self.width() * self.height()

    def clone(self):
        return Rectangle(self.x0, self.y0, self.x1, self.y1)

    def empty(self):
        return self.x0 >= self.x1 and self.y0 >= self.y1

    def pad_by(self, dx, dy):
        assert(not self.empty())
        self.x0 -= dx
        self.y0 -= dy
        self.x1 += dx
        self.y0 += dy

    def shift_by(self, dx, dy):
        assert(not self.empty())
        self.x0 += dx
        self.y0 += dy
        self.x1 += dx
        self.y0 += dy

    def width(self):
        return max(0, self.x1 - self.x0)

    def height(self):
        return max(0, self.y1 - self.y0)

    def include_point(self, x, y):
        if self.empty():
            self.x0 = x
            self.y0 = y
            self.x1 = x + 1
            self.y1 = y + 1
        else:
            self.x0 = min(x, self.x0)
            self.y0 = min(y, self.y0)
            self.x1 = max(x + 1, self.x1)
            self.y1 = max(y + 1, self.y1)

    def include(self, rect):
        if self.empty():
            self.x0 = rect.x0
            self.y0 = rect.y0
            self.x1 = rect.x1
            self.y1 = rect.y1
        else:
            self.x0 = min(self.x0, rect.x0)
            self.y0 = min(self.y0, rect.y0)
            self.x1 = max(self.x1, rect.x1)
            self.y1 = max(self.y1, rect.y1)

    def grow(self, dx, dy):
        return Rectangle(self.x0 - dx, self.y0 - dy, 
                self.x1 + dx, self.y1 + dy)

    def overlaps(self, rect):
        return self.x0 <= rect.x1 and self.x1 >= rect.x0 \
                and self.y0 <= rect.y1 and self.y1 >= rect.y0

    def overlaps_x(self, rect):
        return self.x0 <= rect.x1 and self.x1 >= rect.x0

    def overlaps_y(self, rect):
        return self.y0 <= rect.y1 and self.y1 >= rect.y0

    def contains(self, x, y):
        return x >= self.x0 and x < self.x1 \
                and y >= self.y0 and y < self.y1

    def points(self):
        return (self.x0, self.y0, self.x1, self.y1,)

    def intersection(self, rect):
        if self.empty():
            return self
        return Rectangle(
                max(self.x0, rect.x0),
                max(self.y0, rect.y0),
                min(self.x1, rect.x1),
                min(self.y1, rect.y1)
        )                

    def inclusion(self, rect):
        if self.empty():
            return rect
        return Rectangle(
                min(self.x0, rect.x0),
                min(self.y0, rect.y0),
                max(self.x1, rect.x1),
                max(self.y1, rect.y1)
        ) 
    
    def fraction_covered_by(self, rect):
        isect = self.intersection(rect)
        if self.area():
            return isect.area() / float(self.area())
        else:
            return -1

    @classmethod
    def union_of(cls, *args):
        r = Rectangle(0, 0, 0, 0)
        for arg in args:
            r.include(arg)
        return r            




def r2i(rect):
    return iulib.rectangle(rect.x0, rect.y0, rect.x1, rect.y1)

def i2r(rect):
    return Rectangle(rect.x0, rect.y0, rect.x1, rect.y1)


def smooth(x,window_len=11,window='hanning'):
    """smooth the data using a window with requested size.
    
    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal 
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.
    
    input:
        x: the input signal 
        window_len: the dimension of the smoothing window; should be an odd integer
        window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
            flat window will produce a moving average smoothing.

    output:
        the smoothed signal
        
    example:

    t=linspace(-2,2,0.1)
    x=sin(t)+randn(len(t))*0.1
    y=smooth(x)
    
    see also: 
    
    numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
    scipy.signal.lfilter
 
    TODO: the window parameter could be the window itself if an array instead of a string   
    """

    if x.ndim != 1:
        raise ValueError, "smooth only accepts 1 dimension arrays."
    if x.size < window_len:
        raise ValueError, "Input vector needs to be bigger than window size."
    if window_len<3:
        return x
    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"

    s=numpy.r_[2*x[0]-x[window_len:1:-1],x,2*x[-1]-x[-1:-window_len:-1]]
    #print(len(s))
    if window == 'flat': #moving average
        w=numpy.ones(window_len,'d')
    else:
        w=eval('numpy.'+window+'(window_len)')

    y=numpy.convolve(w/w.sum(),s,mode='same')
    return y[window_len-1:-window_len+1]


def not_char(rect):
    """
    Perform basic validation on a rect to
    test if it *could* be a character box.
    """
    return rect.area() < 4 or rect.area() > 10000 \
            or rect.aspect() < 0.2 or rect.aspect() > 5


def horizontal_overlaps(rect, others, sorted=False):
    """
    Get rects that overlap horizontally with the
    given rect.
    """
    overlaps = []
    for other in others:
        # Note: can optimise to prevent
        # going through the rest of the
        # array when we hit a non match
        if rect.overlaps_y(other):
            overlaps.append(other)
    return overlaps


def get_average_line_height(top_bottoms):
    """
    Tricksy - get height of median line?
    """
    lheights = [b - t for t, b in top_bottoms] 
    lhm = numpy.max(lheights)
    def weight(val):
        return 0 if val < (lhm / 2) else 1
    weights = numpy.vectorize(weight)(lheights)
    return numpy.average(numpy.array(lheights), weights=weights)


def remove_border(narray, average_char_height):
    """
    Try and remove anything that's in a likely
    border region and return the subimage.    
    """
    na = iulib.numpy(narray)
    hpr = na.sum(axis=0)
    vpr = na.sum(axis=1)
    hhp = high_pass_median(hpr, 5.0 / average_char_height)
    vhp = high_pass_median(vpr, 5.0 / average_char_height)

    vidx = vhp.nonzero()[0]
    hidx = hhp.nonzero()[0]

    b = iulib.bytearray()
    iulib.extract_subimage(b, narray, int(vidx[0]), int(hidx[0]),
            int(vidx[-1]), int(hidx[-1]))
    return b




def get_vertical_projection(narray):
    """
    Accumulate image columns.
    """
    return iulib.numpy(narray).sum(axis=1)


def get_horizontal_projection(narray):
    """
    Accumulate image rows.
    """
    return iulib.numpy(narray).sum(axis=0)


def high_pass_max(numpy_arr, maxscale):
    """
    Remove everything below 1/2 of the median
    value.
    """
    # remove noise
    max = numpy.max(numpy_arr)
    def hp(x, m):
        return 0 if x < m else x
    return numpy.vectorize(hp)(numpy_arr, max * maxscale) 


def high_pass_median(numpy_arr, medscale):
    """
    Remove everything below 1/2 of the median
    value.
    """
    # remove noise
    median = numpy.median(numpy_arr)
    def hp(x, m):
        return 0 if x < m else x
    return numpy.vectorize(hp)(numpy_arr, median * medscale) 


def get_lines_by_projection(narray):
    """
    Extract regions of blackness.
    """
    hpr = iulib.numpy(narray).sum(axis=0)
    hps = high_pass_max(hpr, 0.001)

    regions = []
    gotline = None
    count = 0
    for val in hps:
        if val != 0:
            if gotline is None:
                gotline = count                
        else:
            if not gotline is None:
                regions.append((gotline, count))
                gotline = None
        count += 1
    return regions                


def large_or_odd(rect, avg):
    """
    An odd shape.
    """
    return rect.area() > (100 * avg * avg)  or rect.aspect() < 0.2 \
            or rect.aspect() > 10


def strip_non_chars(narray, bboxes, average_height, inverted=True):
    """
    Remove stuff that isn't looking like a character box.
    """
    outboxes = []
    color = 0 if inverted else 255
    for box in bboxes:
        if large_or_odd(box, average_height):
            iulib.fill_rect(narray, box.x0, box.y0, box.x1, box.y1, color)
        else:
            outboxes.append(box)
    return outboxes            
    

def trimmed_mean(numpy_arr, lperc=0, hperc=0):
    """
    Get a trimmed mean value from array, with low and
    high percentage ignored.
    """
    alen = len(numpy_arr)
    return numpy_arr[(alen / 100 * lperc):
            (alen - (alen / 100 * hperc))].mean()
        



class SegmentPageByHintNode(node.Node, generic_nodes.JSONWriterMixin):
    """
    Segment an image using a hint.
    """
    name = "Ocrlab::SegmentPageByHint"
    description = "Segment a page using toplines and column hints"
    arity = 1
    stage = stages.PAGE_SEGMENT
    intypes = [ocrolib.numpy.ndarray]
    outtype = dict
    _parameters = [
        dict(name="toplines", value="0"),
        dict(name="columns", value="1"),
    ]

    def null_data(self):
        """
        Return an empty list when ignored.
        """
        return dict(columns=[], lines=[], paragraphs=[])

    def _eval(self):
        """
        Segment a binary image.

        input: a binary image.
        return: a dictionary of box types:
            lines
            paragraphs
            columns
            images
        """
        input = self.get_input_data(0)
        self.inarray = ocrolib.numpy2narray(input, type='B')
        self.init()

        for topline in range(int(self._params.get("toplines", 0))):
            self.get_header_line()
        self.columns.append(Rectangle.union_of(*self.textlines))
        self.find_columns()
        self.find_lines()
        return dict(
                lines=[r.points() for r in self.textlines],
                columns=[r.points() for r in self.columns]
        )

    def init(self):
        """
        Initialise on receipt of the input.
        """
        # pointer to the region that remains
        # to be segmented - starts at the top
        self.topptr = self.inarray.dim(1)
        
        # obtain an inverted version of the array
        self.inverted = iulib.bytearray()
        self.inverted.copy(self.inarray)        
        iulib.binary_invert(self.inverted)
        self.calc_bounding_boxes()

        # list of extracted line rectangles
        self.textlines = []
        self.columns = []

    def calc_bounding_boxes(self):
        """
        Get bounding boxes if connected components.
        """
        concomps = iulib.intarray()
        concomps.copy(self.inverted)
        iulib.label_components(concomps, False)
        bboxes = iulib.rectarray()
        iulib.bounding_boxes(bboxes, concomps)
        self.boxes = []
        for i in range(bboxes.length()):
            if bboxes.at(i).area() > (self.inverted.dim(0) *
                    self.inverted.dim(1) * 0.95):
                continue
            self.boxes.append(i2r(bboxes.at(i)))

        # get the average text height, excluding  any %%
        self.avgheight = trimmed_mean(numpy.sort(numpy.array(
            [r.height() for r in self.boxes])), 5, 5)

        # remove large or weird boxes from the inverted images
        self.boxes = strip_non_chars(self.inverted, self.boxes, self.avgheight)

    def get_char_boxes(self, boxes):
        """
        Get character boxes.
        """
        return [b for b in boxes if not not_char(b)] 

    def get_header_line(self):
        """
        Get the first found line in an image.
        """
        boxes = self.get_char_boxes(self.boxes)
        # eliminate boxes above our top-of-the-page
        # pointer
        boxes = [b for b in boxes if b.y1 <= self.topptr]
        
        # order boxes by y0 (distance from bottom)
        boxes.sort(lambda x, y: cmp(x.y1, y.y1))
        # reverse so those nearest the top are first
        boxes.reverse()

        # get rects with overlap horizontally with
        # the topmost one
        # try a maximum of 20 lines until we find one with at least
        # 5 overlaps
        overlaps = []
        maxcnt = 0
        line = Rectangle(0, 0, 0, 0)
        while maxcnt < 200 and (len(overlaps) < 2 \
                or line.height() < (self.avgheight * 1.5)):
            overlaps = horizontal_overlaps(
                    boxes[maxcnt], boxes, sorted=False) 
            line = Rectangle.union_of(*overlaps)
            maxcnt += 1

        self.textlines.append(line)

        # set region of interest to below the top line
        self.topptr = line.y0

    def get_possible_columns(self, projection):
        """
        Extract regions of whiteness.
        """
        regions = []
        gotcol = None
        count = 0
        for val in projection:
            if count == len(projection) - 1 and gotcol is not None:
                regions.append(Rectangle(gotcol, 0, count, self.topptr))
            elif val != 0:
                if gotcol is None:
                    gotcol = count                
            else:
                if not gotcol is None:
                    regions.append(Rectangle(gotcol, 0, count, self.topptr))
                    gotcol = None
            count += 1
        return regions

    def filter_columns(self, rects, target):
        """
        Filter a group of regions to match the target
        number, preserving those which seem the most
        likely to be 'good'
        """
        if len(rects) <= target:
            return rects

        # add the x largest cols
        best = []
        for col in sorted(rects, lambda x, y: cmp(y.area(), x.area())):
            best.append(col)
            if len(best) == target:
                break
        return best            

    def find_columns(self):
        """
        Get columns in a section of the image
        """

        portion = iulib.bytearray()
        iulib.extract_subimage(portion, self.inverted, 0, 0, 
                self.inverted.dim(0), self.topptr)
        projection = high_pass_median(iulib.numpy(portion).sum(axis=1), 0.20)
        posscols = self.get_possible_columns(projection)
        bestcols = self.filter_columns(posscols, int(self._params.get("columns", 1)))
        self.columns.extend(bestcols)

    def find_lines(self):
        """
        Get lines in a section of the images.
        """
        for colrect in self.columns:
            newrect = Rectangle(colrect.x0, 0, colrect.x1, self.topptr)
            if newrect.area() < 1:
                continue
            portion = iulib.bytearray()
            iulib.extract_subimage(portion, self.inverted, *newrect.points())
            regions = get_lines_by_projection(portion)
            plines = []
            for bottom, top in regions:
                height = top - bottom
                if height - self.avgheight < self.avgheight / 2:
                    continue
                plines.append(Rectangle(colrect.x0, bottom, colrect.x1, top))

            cpline = None
            clline = Rectangle(0, 0, 0, 0)
            charboxes = self.get_char_boxes(self.boxes)
            colboxes = [b for b in charboxes \
                    if b.overlaps(colrect.grow(10, 10))]
            colboxes.sort(lambda x, y: cmp(x.y1, y.y1))
            colboxes.reverse()

            clines = []
            for p in plines:
                clines.append(Rectangle(0, 0, 0, 0))

            while colboxes:
                char = colboxes.pop(0)
                cline = Rectangle(0, 0, 0, 0)
                for i in range(len(plines)):
                    pline = plines[i]
                    if char.overlaps(pline):
                        clines[i].include(char)
            self.textlines.extend(clines)


class SegmentPageManualNode(node.Node, generic_nodes.JSONWriterMixin):
    """
    Segment an image using column boxes.
    """
    name = "Ocrlab::SegmentPageManual"
    description = "Segment a page using manual column definitions"
    arity = 1
    stage = stages.PAGE_SEGMENT
    intypes = [ocrolib.numpy.ndarray]
    outtype = dict
    _parameters = [
        dict(name="boxes", value=""),
    ]

    def __init__(self, *args, **kwargs):
        super(SegmentPageManualNode, self).__init__(*args, **kwargs)
        self._regions = ocrolib.RegionExtractor()
        self._segmenter = ocrolib.SegmentPageByRAST1()

    def null_data(self):
        """
        Return an empty list when ignored.
        """
        return dict(columns=[], lines=[], paragraphs=[])

    def _eval(self):
        """
        Segment a binary image.

        input: a binary image.
        return: a dictionary of box types:
            lines
            paragraphs
            columns
            images
        """
        page_bin = self.get_input_data(0)
        coords = self.get_coords();
        if len(coords) == 0:
            coords.append(Rectangle(0, 0, 
                page_bin.shape[1] - 1, page_bin.shape[0] - 1))
        self.sanitise_coords(coords, page_bin.shape[1], page_bin.shape[0]);            
        height = page_bin.shape[1]
        boxes = {}
        for rect in coords:
            points = rect.points()
            col = ocrolib.iulib.bytearray()
            ocrolib.iulib.extract_subimage(col, ocrolib.numpy2narray(page_bin), *points)
            pout = self.segment_portion(col, height, points[0], points[1])
            for key, rects in pout.iteritems():
                if boxes.get(key) is not None:
                    boxes.get(key).extend([r.points() for r in rects])
                else:
                    boxes[key] = [r.points() for r in rects]
        return boxes

    def segment_portion(self, portion, height, dx, dy):
        """
        Segment a single-column chunk.
        """
        page_seg = self._segmenter.segment(ocrolib.narray2numpy(portion))
        return self.extract_boxes(self._regions, page_seg, height, dx, dy)

    def get_coords(self):
        """
        Return a list of rects from the coords string.
        """
        strlist = self._params.get("boxes", "")
        if strlist is None:
            return []
        rstr = strlist.split("~")
        rects = []
        for r in rstr:
            points = r.split(",")
            if len(points) != 4:
                continue
            try:
                ints = [int(i) for i in points]
                assert len(ints) == 4
                rects.append(Rectangle(*ints))
            except ValueError:
                continue
        return rects

    @classmethod
    def sanitise_coords(cls, rectlist, width, height):
        """
        Treat negative numbers as the outer bound.
        """
        for i in range(len(rectlist)):
            rect = rectlist[i]
            rect.x0 = max(rect.x0, 0)
            rect.y0 = max(rect.y0, 0)
            if rect.x1 < 0:
                rect.x1 = width
            if rect.y1 < 0:
                rect.y1 = height
            if rect.x0 > width:
                rect.x0 = width - 1
            if rect.y0 > height:
                rect.y0 = height - 1
            if rect.x1 > width:
                rect.x1 = width
            if rect.y1 > height:
                rect.y1 = height            
            rectlist[i] = rect

    @classmethod
    def extract_boxes(cls, regions, page_seg, height, dx, dy):
        """
        Extract line/paragraph geoocrolib.metry info.
        """
        out = dict(columns=[], lines=[], paragraphs=[])
        #out = dict(lines=[], paragraphs=[])
        exfuncs = dict(lines=regions.setPageLines,
                paragraphs=regions.setPageParagraphs)
                #columns=regions.setPageColumns)
        #page_seg = numpy.flipud(page_seg)
        for box, func in exfuncs.iteritems():
            func(page_seg)
            for i in range(1, regions.length()):
                out[box].append(Rectangle(regions.x0(i) + dx,
                    (regions.y0(i)) + dy, regions.x1(i) + dx,
                    (regions.y1(i)) + dy))
        return out



class Manager(manager.StandardManager):
    """
    Handle Ocrlab nodes.
    """
    @classmethod
    def get_node(self, name, **kwargs):
        if name.find("::") != -1:
            name = name.split("::")[-1]
        if name == "SegmentPageByHint":
            return SegmentPageByHintNode(**kwargs)
        elif name == "SegmentPageManual":
            return SegmentPageManualNode(**kwargs)

    @classmethod
    def get_nodes(cls, *oftypes):
        return super(Manager, cls).get_nodes(
                *oftypes, globals=globals())


if __name__ == "__main__":
    for n in Manager.get_nodes():
        print n



