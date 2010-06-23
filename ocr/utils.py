"""
Generic OCR helper functions and wrapper around various OCRopus
and Tesseract tools.
"""

import os
from datetime import datetime
import shutil
import tempfile
import subprocess as sp
import UserDict
import ocropus
import iulib


def get_tesseract():
    """
    Try and find where Tesseract is installed.
    """
    return sp.Popen(["which", "tesseract"], 
            stdout=sp.PIPE).communicate()[0].strip()


def save_ocr_images(images, basepath, temp=True):
    """
    Save OCR images to the media directory...
    """                         
    paths = []
    if temp:
        basepath = os.path.join(basepath, "temp")
    basepath = os.path.join(basepath, datetime.now().strftime("%Y%m%d%H%M%S"))
    if not os.path.exists(basepath):
        os.makedirs(basepath, 0777)

    for _, handle in images:
        path = os.path.join(basepath, handle.name)
        with open(path, "wb") as outfile:
            for chunk in handle.chunks():
                outfile.write(chunk)
            paths.append(path)
    return paths


def convert_to_temp_image(imagepath, suffix="tif"):
    """
    Convert PNG to TIFF with GraphicsMagick.  This seems
    more reliable than PIL, which seems to have problems
    with Group4 TIFF encoders.
    """
    raise ExternalToolError("Test Error")
    with tempfile.NamedTemporaryFile(suffix=".%s" % suffix) as tmp:
        tmp.close()
        retcode = sp.call(["convert", imagepath, tmp.name])
        if not retcode == 0:
            raise ExternalToolError(
                "convert failed to create TIFF file with errno %d" % retcode) 
        return tmp.name


def output_to_plain_text(jsondata):
    """
    Convert page json to plain text.
    """
    return " ".join([line["text"] for line in jsondata["lines"]])


def get_converter(engine_type, logger, params):
    """
    Get the appropriate class to do the conversion.
    """
    if engine_type == "ocropus":
        return OcropusWrapper(logger, params)
    else:
        return TessWrapper(logger, params)



class OcropusError(StandardError):
    """
    Ocropus-related exceptions.
    """
    pass


class ExternalToolError(StandardError):
    """
    Errors with external command-line tools etc.
    """
    pass


class OcropusParams(UserDict.DictMixin):
    """
    Convert a dictionary into an object with certain
    default attribites.  It also uses encode() to convert
    Django unicode strings to standard strings with the 
    Ocropus python bindings can handle.
    """
    def __init__(self, dct):
        self.lmodel = ""
        self.cmodel = ""
        self.pseg = "SegmentPageByRAST"
        self.clean = "StandardPreprocessing"

        for key, val in dct.iteritems():
            if isinstance(val, (list, tuple)):
                setattr(self, str(key), [x if isinstance(x, dict) \
                    else self._safe(x) for x in val])
            else:
                setattr(self, str(key), val if isinstance(val, dict) \
                    else self._safe(val))

    def keys(self):
        """Dictionary keys."""
        return self.__dict__.keys()

    def _safe(self, param):
        """Convert unicode strings to safe values."""
        if isinstance(param, unicode):
            return param.encode()
        else:
            return param

    def __getitem__(self, item):
        """Slice notation."""
        return self.__dict__[item]

    def __repr__(self):
        """Generic representation."""
        return "<%s: %s>" % (self.__class__.__name__, self.__dict__)


class OcropusWrapper(object):
    """
    Wrapper around OCRopus's basic page-recognition functions so
    that bits and peices can be reused more easily.
    """
    def __init__(self, logger, params):
        """
        Initialise an OcropusWrapper object.
        """
        self._linerec = None
        self._lmodel = None
        self.logger = logger
        self.params = OcropusParams(params)
        self.init()


    def init(self):
        """
        Load the line-recogniser and the lmodel FST objects.
        """
        try:
            self._linerec = ocropus.load_linerec(self.params.cmodel)
            self._lmodel = ocropus.make_OcroFST()
            self._lmodel.load(self.params.lmodel)
        except (StandardError, RuntimeError), err:
            raise err
            
    
    def convert(self, filepath, callback=None, **cbkwargs):
        """
        Convert an image file into text.  A callback can be supplied that
        is evaluated before every individual page line is run.  If it does
        not evaluate to True the function returns early with the page 
        results gathered up to that point.  Keyword arguments can also be
        passed to the callback.
        """
        page_bin = self.get_page_binary(filepath)
        page_seg = self.get_page_seg(page_bin)
        pagewidth = page_seg.dim(0)
        pageheight = page_seg.dim(1)
        
        self.logger.info("Extracting regions...")
        regions = ocropus.RegionExtractor()
        regions.setPageLines(page_seg)
        
        self.logger.info("Recognising lines...")
        pagedata = { 
            "page" : os.path.basename(filepath) ,
            "lines": [],
            "box": [0, 0, pagewidth, pageheight]
        }
        for i in range(1, regions.length()):
            # test for continuation
            if callback is not None:
                if not callback(**cbkwargs):
                    return pagedata

            line = iulib.bytearray()
            regions.extract(line, page_bin, i, 1)        
            bbox = [regions.x0(i), pageheight - regions.y0(i),
                regions.x1(i) - regions.x0(i), regions.y1(i) - regions.y0(i)]
            try:
                text = self.get_transcript(line)
            except StandardError:
                text = ""
            pagedata["lines"].append({"line": i, "box": bbox, "text" : text })
        return pagedata


    def get_page_binary(self, filepath):
        """
        Convert an on-disk file into an in-memory iulib.bytearray.
        """
        page_gray = iulib.bytearray()
        iulib.read_image_gray(page_gray, filepath)        
        self.logger.info("Binarising image with %s" % self.params.clean)
        preproc = ocropus.make_IBinarize(self.params.clean)
        page_bin = iulib.bytearray()
        preproc.binarize(page_bin, page_gray)
        return page_bin


    def get_page_seg(self, page_bin):
        """
        Segment the binary page into a colour-coded segmented images.
        """
        self.logger.info("Segmenting page with %s" % self.params.pseg)
        segmenter = ocropus.make_ISegmentPage(self.params.pseg)
        page_seg = iulib.intarray()
        segmenter.segment(page_seg, page_bin)
        return page_seg


    def get_transcript(self, line):
        """
        Run line-recognition on an iulib.bytearray images of a 
        single line.
        """
        fst = ocropus.make_OcroFST()
        self._linerec.recognizeLine(fst, line)
        result = iulib.ustrg()
        # NOTE: This returns the cost - not currently used
        ocropus.beam_search(result, fst, self._lmodel, 1000)
        return result.as_string()





class TessWrapper(OcropusWrapper):
    """
    Override certain methods of the OcropusWrapper to
    use Tesseract for recognition of individual lines.
    """
    def __init__(self, *args, **kwargs):
        """
        Initialise a TessWrapper object.
        """
        self._tessdata = None
        self._lang = None
        self._tesseract = None
        super(TessWrapper, self).__init__(*args, **kwargs)


    def init(self):
        """
        Extract the lmodel to a temporary directory.  This is
        cleaned up in the destructor.
        """
        if self.params.lmodel and self._tessdata is None:
            self.unpack_tessdata(self.params.lmodel)
        self._tesseract = get_tesseract()


    def get_transcript(self, line):
        """
        Recognise each individual line by writing it as a temporary
        PNG, converting it to Tiff, and calling Tesseract on the
        image.  Unfortunately I can't get the current stable 
        Tesseract 2.04 to support anything except TIFFs.
        """
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            tmp.close()
            iulib.write_image_binary(tmp.name, line)
            tiff = convert_to_temp_image(tmp.name, "tif")
            text = self.process_line(tiff)
            os.unlink(tmp.name)
            os.unlink(tiff)
            return text            


    def unpack_tessdata(self, lmodelpath):
        """
        Unpack the tar-gzipped Tesseract language files into
        a temporary directory and set TESSDATA_PREFIX environ
        var to point at it.
        """
        # might as well make this even less efficient!
        self.logger.info("Unpacking tessdata: %s" % lmodelpath)
        import tarfile
        self._tessdata = tempfile.mkdtemp() + "/"
        datapath = os.path.join(self._tessdata, "tessdata")
        os.mkdir(datapath)
        # let this throw an exception if it fails.
        tgz = tarfile.open(lmodelpath, "r:*")
        self._lang = os.path.splitext(tgz.getnames()[0])[0]
        tgz.extractall(path=datapath)
        tgz.close()

        # set environ var where tesseract picks up the tessdata dir
        # this DOESN'T include the "tessdata" part
        os.environ["TESSDATA_PREFIX"] = self._tessdata


    def process_line(self, imagepath):
        """
        Run Tesseract on the TIFF image, using YET ANOTHER temporary
        file to gather the output, which is then read back in.  If
        you think this seems horribly inefficient you'd be right, but
        Tesseract's external interface is quite inflexible.
        TODO: Fix hardcoded path to Tesseract.
        """
        lines = []
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.close()
            tessargs = ["/usr/local/bin/tesseract", imagepath, tmp.name]
            if self._lang is not None:
                tessargs.extend(["-l", self._lang])                
            proc = sp.Popen(tessargs, stderr=sp.PIPE)
            err = proc.stderr.read()
            if proc.wait() != 0:
                raise RuntimeError(
                    "tesseract failed with errno %d: %s" % (
                        proc.returncode, err))
            
            # read and delete Tesseract's temp text file
            # whilst writing to our file
            with open(tmp.name + ".txt", "r") as txt:
                lines = [line.rstrip() for line in txt.readlines()]
                if lines and lines[-1] == "":
                    lines = lines[:-1]
                os.unlink(txt.name)        
        return " ".join(lines)


    def __del__(self):
        """
        Cleanup temporarily-extracted lmodel directory.
        """
        if self._tessdata and os.path.exists(self._tessdata):
            try:
                self.logger.info(
                    "Cleaning up temp tessdata folder: %s" % self._tessdata)
                shutil.rmtree(self._tessdata)
            except OSError, (errno, strerr):
                self.logger.error(
                    "RmTree raised error: %s, %s" % (errno, strerr))

