#!/usr/local/bin/python3.4
import flask
import urllib.request
import urllib.error
import re
import math
import lxml
from lxml.html import HTMLParser, document_fromstring, make_links_absolute, tostring
import hashlib
import cv2
import numpy as np
import collections
import os, sys, tempfile, shutil, contextlib
import mimetypes
from PIL import Image


app = flask.Flask(__name__)
app.secret_key = 'ECE36400sbayapur'
DIR_ROOT = os.path.dirname(os.path.abspath(__file__))
DIR_STATIC = os.path.join(DIR_ROOT,'static')

@app.route('/')
def root_page():
    return flask.render_template('root.html')

@app.route('/view/')
def view_page():
    url = flask.request.args.get('url')
    expr = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ])'
    m = re.match(expr, url)
    if m == None:
        #return "URL is Invalid"
        flask.flash("URL is Invalid")
        return flask.redirect(flask.url_for('root_page')) #Credit: Adapted from http://flask.pocoo.org/docs/1.0/patterns/flashing/
    socialList = ["facebook", "whatsapp", "tumblr", "instagram", "twitter", "youtube", "flickr", "linkedin", "pinterest", "plus.google"]
    for sSite in socialList:
        if sSite in url:
            #return "url contains social networking Site " + sSite
            flask.flash("url contains social networking Site " + sSite)
            return flask.redirect(flask.url_for('root_page')) #Credit: Adapted from http://flask.pocoo.org/docs/1.0/patterns/flashing/
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'PurdueUniversityClassProject/1.0 (sbayapur@purdue.edu https://goo.gl/dk8u5S)')
        response = urllib.request.urlopen(req)
        the_page = response.read().decode('utf-8')
        parser = HTMLParser(encoding="UTF-8")
        root = document_fromstring(the_page, parser=parser, base_url=url)
        root.make_links_absolute(url, resolve_base_href=True)
        #the_page = tostring(root)
        imgurl = copy_profile_photo_to_static(root)

        if imgurl is None:
            print("No Image exists with a face")
            return the_page
        #print(imgurl)
        imgFileName = os.path.join(DIR_STATIC, imgurl)
        #print(imgFileName)
        #return flask.redirect(imgurl)
        imageDim = get_image_info(imgFileName)
        listofRect = imageDim.get("faces")
        add_glasses(imgFileName, listofRect[0])
        static_url = flask.url_for('static', filename=imgurl, _external=True)
        #print(static_url)
        if 'gif' in static_url:
            static_url = static_url[:-3] + "jpeg"
        imgNode = get_profile_photo_node(root,imgurl)
        if imgNode == 'None':
            print("No Image node exists with a Face")
            return the_page
        x = imgNode.values()
        for y in x:
          if 'http' in y:  # look for image url
           old_url = y
           break
        #Credit: Adapted from note https://piazza.com/class/jkspuifikh3s9?cid=783
        imgNode.set("src", static_url)


        the_page = lxml.etree.tostring(root,method="html")
        return the_page
    except urllib.error.URLError:
        return "URL not found"
    except TypeError:
        print("TypeError on the Page")
        return the_page
    except OSError:
        print("OSError on the Page")
        return the_page

def make_filename(url, extension):
    strHash = url + extension;
    #print(strHash)
    return hashlib.sha1(strHash.encode("utf8")).hexdigest()

@contextlib.contextmanager
def fetch_images(etree):
    with pushd_temp_dir():
        filename_to_node = collections.OrderedDict()
        #
        # Extract the image files into the current directory
        #  Adapted from Lab 12
        extension = '.jpg'
        for node in etree.iter():
            if (node.tag == "img"):
                x = node.values()
                for y in x:
                    if 'http' in y:  #look for image url
                        imageURL = y
                        break;
                #print(imageURL)
                image_hash = make_filename(imageURL, extension)
                try:
                    response = urllib.request.urlopen(imageURL)
                    response2 = response.read()
                    extension = mimetypes.guess_extension(response.info().get("Content-type"))
                    with open(os.path.join(os.getcwd(), image_hash + extension), "wb") as infile:
                        infile.write(response2)
                        ihext = os.path.join(os.getcwd(), image_hash+extension)
                        filename_to_node[ihext] = node
                except ValueError:
                    print("Invalid Image Type")
        yield filename_to_node

@contextlib.contextmanager
def pushd_temp_dir(base_dir=None, prefix="tmp.hpo."):
    '''
    Create a temporary directory starting with {prefix} within {base_dir}
    and cd to it.

    This is a context manager.  That means it can---and must---be called using
    the with statement like this:

        with pushd_temp_dir():
            ....   # We are now in the temp directory
        # Back to original directory.  Temp directory has been deleted.

    After the with statement, the temp directory and its contents are deleted.


    Putting the @contextlib.contextmanager decorator just above a function
    makes it a context manager.  It must be a generator function with one yield.

    - base_dir --- the new temp directory will be created inside {base_dir}.
                   This defaults to {main_dir}/data ... where {main_dir} is
                   the directory containing whatever .py file started the
                   application (e.g., main.py).

    - prefix ----- prefix for the temp directory name.  In case something
                   happens that prevents
    '''
    if base_dir is None:
        proj_dir = sys.path[0]
        # e.g., "/home/ecegridfs/a/ee364z15/hpo"

        main_dir = os.path.join(proj_dir, "data")
        # e.g., "/home/ecegridfs/a/ee364z15/hpo/data"

        # Create temp directory
        temp_dir_path = tempfile.mkdtemp(prefix=prefix, dir=main_dir)

        try:
            start_dir = os.getcwd()  # get current working directory
            os.chdir(temp_dir_path)  # change to the new temp directory

            try:
                yield
            finally:
                # No matter what, change back to where you started.
                os.chdir(start_dir)
        finally:
            # No matter what, remove temp dir and contents.
            shutil.rmtree(temp_dir_path, ignore_errors=True)

def get_image_info(filename):
    imageDim = dict()
    # Credit: Adapted from example from url https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_core/py_basic_ops/py_basic_ops.html
    if 'gif' in filename:
        img = Image.open(filename)
        filename = filename[:-3] + "jpeg"
        img.convert('RGB').save(filename, 'jpeg')
    img = cv2.imread(filename)
    # get image properties.
    t = np.shape(img)   #Adpated End
    if(len(t) > 0):
        imageDim["w"] = t[1]
        imageDim["h"] = t[0]
        FACE_DATA_PATH = "/home/ecegridfs/a/ee364/site-packages/cv2/data/haarcascade_frontalface_default.xml"
        #FACE_DATA_PATH = "C:/Users/bayapure/PycharmProjects/hpo/haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(FACE_DATA_PATH)
        cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(img, 1.3, 5)
        #print(faces)
        fList = []
        if len(faces) >= 1:
            for f in faces:
                fDict = {}
                fDict["x"] = f[0]
                fDict["y"] = f[1]
                fDict["w"] = f[2]
                fDict["h"] = f[3]
                fList.append(fDict)
        fList.sort(key=lambda x: x.get("w"), reverse=True)  #sort is width
        imageDim["faces"] = fList
    return imageDim

def find_profile_photo_filename(filename_to_etree):
    cSize = 0
    cElement = None
    for key, value in filename_to_etree.items():
        imageDim = get_image_info(key)
       # print(imageDim)
        listofRectangles = imageDim.get('faces')
        if len(listofRectangles) == 1:  # if there is only one rectangle that could be profile photo
            rect = listofRectangles[0]
            #Calculate Sum of dimensions
            size = imageDim.get('w') + imageDim.get('h') #take the one with bigger width and height
            if size >= cSize:
                cSize = size
                cElement = key
    if cElement is None:  # if cElement is still None no Image exists with one face look for image with multiple faces
        for key, value in filename_to_etree.items():
            imageDim = get_image_info(key)
            listofRectangles = imageDim.get('faces')
            if len(listofRectangles) > 1:
                rect = listofRectangles[0]  # Take first face
                # Calculate Sum of dimensions
                size = imageDim.get('w') + imageDim.get('h')  #take image with bigger width and height
                if size >= cSize:
                    cSize = size
                    cElement = key
    return cElement

def copy_profile_photo_to_static(etree):
    with fetch_images(etree) as f:
        fName = find_profile_photo_filename(f)
        #print(fName)
        if fName is None:
            return None
       #c_dir = os.getcwd() + "/static" get working directory is not working for some cases when there are too many images on the page
        c_dir = DIR_STATIC
        try:
            fcPath = os.path.basename(fName)
            shutil.copy(fName, c_dir)
        except IOError as e:
            print("Unable to copy file. %s" % e)
        #static_url = flask.url_for('static', filename=fcPath)
    return fcPath

def get_profile_photo_node(etree, imgurl):
    with fetch_images(etree) as f:
        for key, value in f.items():
            if imgurl in key:
                return value
        return None

def add_glasses(filename, face_info):

    EYE_DATA = "/home/ecegridfs/a/ee364/site-packages/cv2/data/haarcascade_eye.xml"
   #EYE_DATA = "C:/Users/bayapure/PycharmProjects/hpo/haarcascade_eye.xml"
    if 'gif' in filename:
        filename = filename[:-3] + "jpeg"
    #print(filename)
    img = cv2.imread(filename)
    eye_cascade = cv2.CascadeClassifier(EYE_DATA)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    w = face_info.get("w")
    h = face_info.get("h")
    x = face_info.get("x")
    y = face_info.get("y")

    hat_regionx = w //5
    hat_regiony = h//5
    cv2.rectangle(img, (x-int(.5*hat_regionx), y-int(.7*hat_regiony)), (x+w+int(.5*hat_regionx),y),(255,0,0),cv2.FILLED)
    cv2.rectangle(img, (x+int(.2*hat_regionx), y-int(2.5*hat_regiony)), (x+w-int(.3*hat_regionx),y-int(0.5*hat_regiony)),(255,0,0),cv2.FILLED)
    # Credit: Adapted from example from url  https://docs.opencv.org/3.4/d7/d8b/tutorial_py_face_detection.html
    #roi_grey = img[y:y+h, x:x+w]
    #roi_color = img[y:y+h, x:x+w]
    eyes = eye_cascade.detectMultiScale(img_gray, 1.3, 5)   #Adapted End
    #print(eyes)
    eye_top = int(y+.25*h)
    eye_bottom = int(y+.55*h)
    #print(eye_top)
    #print(eye_bottom)
    eyes2 = []
    for (x2,y2,w2,h2) in eyes:
        if(y2 >= eye_top and (h2+y2) <= eye_bottom):
            eyes2.append({"ex":x2, "ey":y2, "ew":w2, "eh":h2})
    eyes2.sort(key= lambda i: i["ew"]*i["eh"], reverse = True)
    eye_pair = []
    if(len(eyes2) >=2):
        for i in range(0, len(eyes2)):
            for j in range (i+1, len(eyes2)):
                if abs(eyes2[i]["ey"] - eyes2[j]["ey"]) < 20:
                    eye_pair.append((eyes2[i],eyes2[j]))
                    break
    if(len(eyes2) ==1):
        second_x = x + (w//2)+ (eyes2[0]["ex"]-x)
        eye_pair.append((eyes2[0], {"ex": second_x, "ey": eyes2[0]["ey"], "ew": eyes2[0]["ew"], "eh": eyes2[0]["eh"]}))
    if(len(eyes2) == 0):
        face_x = w //5
        face_y = h//5
        eye_1 = {"ex": face_x+x , "ey": int(face_y*1.5)+ y, "ew": face_x,  "eh": face_y}
        eye_2 = {"ex": int(3*face_x+x), "ey": int(1.5*face_y) + y, "ew": face_x, "eh":face_y}
        eye_pair.append((eye_1, eye_2))
    if (len(eye_pair) == 0):
        if(len(eyes2) > 0):
            if eyes2[-1]["ex"] < (x+w//2):
                eye_pair.append((eyes2[-1], {"ex": eyes2[-1]["eh"] + 2*w//5, "ey":eyes2[-1]["ey"], "ew":eyes2[-1]["ew"], "eh":eyes2[-1]["eh"]}))
            else:
                eye_pair.append((eyes2[-1], {"ex": eyes2[-1]["eh"] + 2*w//5, "ey":eyes2[-1]["ey"], "ew":eyes2[-1]["ew"], "eh":eyes2[-1]["eh"]}))
    #print(eye_pair)

    #cv2.imshow('img', img)
    #cv2.waitKey(0)
    get_eyes = eye_pair[0]
    #print(get_eyes)
    first_eye = get_eyes[0]
    second_eye = get_eyes[1]
    #print(first_eye)
    ex1 = first_eye.get("ex")
    ex2 = second_eye.get("ex")
    if ex2 < ex1:
        temp = first_eye
        first_eye = second_eye
        second_eye = temp
    ex1 = first_eye.get("ex")
    ex2 = second_eye.get("ex")
    #print(ex1)
    ey1 = first_eye.get("ey")
    ew1 = first_eye.get("ew")
    eh1 = first_eye.get("eh")
    #cv2.rectangle(img, (ex1,ey1), (ex1 + ew1, ey1+eh1),(0,255,0),2)
    cx = math.ceil(ex1 + ew1/2)
    cy = math.ceil(ey1 + eh1/2)
    cr = math.ceil(ew1/2)
    lx = ex1
    lx_x =math.ceil(ex1 - ew1/1.5)
    ly =math.ceil(ey1+(ew1/2))
    cv2.line(img,(lx,ly),(lx_x,ly-3),(255,0,0),2)

    #print(second_eye)
    #print(ex2)
    ey2 = second_eye.get("ey")
    ew2 = second_eye.get("ew")
    eh2 = second_eye.get("eh")
    #cv2.rectangle(img, (ex1,ey1), (ex1 + ew1, ey1+eh1),(0,255,0),2)
    cx2 = math.ceil(ex2 + ew2/2)
    cy2 = math.ceil(ey2 + eh2/2)
    cr2 = math.ceil(ew2/2)
    if(cr > cr2):
        cv2.circle(img, (cx,cy), cr, (0,255,0), 2)
        cv2.circle(img, (cx2,cy2), cr, (0,255,0), 2)
    else:
        cv2.circle(img, (cx,cy), cr2, (0,255,0), 2)
        cv2.circle(img, (cx2,cy2), cr2, (0,255,0), 2)

    lx2 = ex2+ew2
    ly2 = math.ceil(ey2+ew2/2)
    lx_x2 = math.ceil(lx2+ ew2/1.5)
    cv2.line(img,(lx2,ly),(lx_x2,ly2-3),(255,0,0),2)
    #cv2.imshow('img', img)
    #cv2.waitKey(0)
    lx3 = ex1+ew1+4
    lx4 = ex2-4
    cv2.line(img, (lx3,ly-3),(lx4, ly-3), (255,0,0), 2)
    cv2.imwrite(filename, img)

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=os.environ.get("ECE364_HTTP_PORT", 8000),
            use_reloader=True, use_evalex=False, debug=True, use_debugger=False)
    # Each student has their own port, which is set in an environment variable.
    # When not on ecegrid, the port defaults to 8000.  Do not change the host,
    # use_evalex, and use_debugger parameters.  They are required for security.
    #
    # Credit:  Alex Quinn.  Used with permission.  Preceding line only.
