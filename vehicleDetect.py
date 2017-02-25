import numpy as np
import cv2
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import glob
import os
import random
from skimage.feature import hog
import csv
import sys
import pickle
from sklearn.externals import joblib
from sklearn.preprocessing import StandardScaler
from scipy.ndimage.measurements import label
from moviepy.editor import VideoFileClip, ImageSequenceClip
import vehicleDetectUtil as vehicleUtil
import vehicleDetect_svmVar as svmVar


# GLOBALS
cnn_model = 'cnn_100e.h5'

# sliding windows
#windowSizes = [96, 128, 145]
windowSizes = [96, 145]
#windowSizes_cnn = [64, 96, 120]
windowSizes_cnn = [64, 96, 120]
#imgScales = [0.65, 0.45]
imgScales = [1., 0.8, 0.65, 0.45]
windowOverlap = 0.8
windowOverlap_cnn = 0.65
heatThreshPerFrame_cnn = 1
heatThresh_cnn = 4
heatThreshPerFrame_svm = 1
heatThresh_svm= 4
# classifier
classifier_imgSize = 64

heatmap_arr = []
heatmap_filterSize = 8
outputDebug = True
writeGridsImgs = False
rawOutput = False

def process_frame_efficient(img, debug=False):
    # sliding windows creation
    global windowSizes
    global heatmap_arr
    windowSizes = [64]
    heat = np.zeros_like(img[:,:,0]).astype(np.float)
    img_size = img.shape
    windows = []
    imgs = []
    if method == 'svm':
        imgCvt = vehicleUtil.convertClrSpace(img, clrspaceOrigin='RGB', colorspace='YCrCb')
        fac_i = 0
        if writeGridsImgs:
            windowImg = np.copy(img)
        for scaleFac in imgScales:
            inverseFac = 1/scaleFac
            x_scaled = int(img.shape[1]*scaleFac)
            y_scaled = int(img.shape[0]*scaleFac)
            img_scaled = cv2.resize(imgCvt, (x_scaled, y_scaled))
            img_scaled_size = img_scaled.shape
            x_start_stop = [int(img_scaled_size[1]/2), img_scaled_size[1]]
            #x_start_stop = [0, img_scaled_size[1]]
            y_start = int(img_scaled_size[0]/2)+30
            #y_stop = (img_scaled_size[0]-int(70*scaleFac))
            y_stop = img_scaled_size[0]-70
            y_size = y_stop - y_start
            # allow window sizes of different scales in areas that make sense in the image plane
            if fac_i == 0:
                y_stop = y_start + (y_size * min(1.2-scaleFac, 1.))
                y_start = y_start + ((1-scaleFac)*300)
            elif fac_i == 1:
                y_stop = y_start + (y_size * min(1.4-scaleFac, 1.))
                y_start = y_start + ((1-scaleFac)*200)

            y_start_stop = [y_start, y_stop]
            
            windows_atScale = vehicleUtil.slide_window(img_scaled, x_start_stop=x_start_stop, y_start_stop=y_start_stop, windowSizeAr=[64], xy_overlap=(windowOverlap, windowOverlap))
            # save bounding box in original image space
            for each in windows_atScale:
                windows.append(((int(each[0][0]*inverseFac), int(each[0][1]*inverseFac)), (int(each[1][0]*inverseFac), int(each[1][1]*inverseFac))))
                if writeGridsImgs:
                    windowImg = vehicleUtil.draw_boxes(windowImg, [windows[-1]], color=(0, 0, 255), thick=6)
            if writeGridsImgs:
                cv2.imwrite('windows_fac{}.jpg'.format(fac_i), windowImg)
                windowImg = np.copy(img)
            fac_i += 1
            if debug:
                print('extracting windows at scale...')
            imgs.extend(vehicleUtil.get_window_imgs(img_scaled, windows_atScale, classifier_imgSize, resize=True))
        svc = joblib.load('svm.pkl')
        X_scaler = joblib.load('svm_scaler.pkl')
        #pca = joblib.load('svm_pca.pkl')
        if debug:
            print('SVM: extracting windows...')
        '''
        print('SVM: extracting HOG features...')
        hogImg = vehicleDetectUtil.convertClrSpace(img, colorspace=svmVar.spatial_clr)
        hog_array = []
        for channel in svmVar.hog_channel:
            hog_array.append(hog(hogImg[:,:,channel], orientations=svmVar.orient, pixels_per_cell=(svmVar.pix_per_cell, svmVar.pix_per_cell), cells_per_block=(svmVar.cell_per_block, svmVar.cell_per_block), visualise=False, feature_vector=False))           
        '''
        if debug:
            print('SVM: extracting features/ predicting...')
        # awkward: setting colorspace to BGR to circumvent cvtColor call
        features = vehicleUtil.extract_features(imgs, hogArr=None, readImg=False, cspace='BGR', spatial_size=(svmVar.spatial, svmVar.spatial),
                                hist_bins=svmVar.histbin, hist_range=(0, 256), spatialFeat = svmVar.spatialFeat, histFeat = svmVar.histFeat,
                                hogFeat=svmVar.hogFeat, hog_cspace='BGR', hog_orient=svmVar.orient, hog_pix_per_cell=svmVar.pix_per_cell, hog_cell_per_block=svmVar.cell_per_block, hog_channel=svmVar.hog_channel)
        X = np.vstack((features)).astype(np.float64)
        scaled_X = X_scaler.transform(X)
        #scaled_X = pca.transform(scaled_X)
        pred_bin = svc.predict(scaled_X)
        #pred = svc.decision_function(scaled_X)
        #pred_bin = np.zeros(len(scaled_X))
        #print(max(pred))
        #pred_bin[pred > 1.] = 1
    elif method == 'cnn':
        windows = []
        x_start_stop = [640, 1090]
        ystart = 360+53
        ystop = ystart+60
        y_start_stop = [ystart, ystop]
        windows.extend(vehicleUtil.slide_window(img, x_start_stop=x_start_stop, y_start_stop=y_start_stop, windowSizeAr=[windowSizes_cnn[0]], xy_overlap=(windowOverlap_cnn, windowOverlap_cnn)))
        x_start_stop = [640, img_size[1]]
        y_start_stop = [360+50, 720-220] # 200 was good enough
        windows.extend(vehicleUtil.slide_window(img, x_start_stop=x_start_stop, y_start_stop=y_start_stop, windowSizeAr=[windowSizes_cnn[1]], xy_overlap=(windowOverlap_cnn, windowOverlap_cnn)))
        x_start_stop = [640, img_size[1]]
        y_start_stop = [500, 720-70]
        windows.extend(vehicleUtil.slide_window(img, x_start_stop=x_start_stop, y_start_stop=y_start_stop, windowSizeAr=[windowSizes_cnn[2]], xy_overlap=(windowOverlap_cnn, windowOverlap_cnn)))
        imgs = vehicleUtil.get_window_imgs(img, windows, classifier_imgSize)
        pred = model.predict(imgs)
        pred_bin = np.array([x[0] for x in pred])
        pred_bin = np.where(pred_bin > 0.5, 1, 0)
    if debug:
        print('plotting hot windows...')
    ind = [x for x in range(len(pred_bin)) if pred_bin[x]==1]
    hot_windows = [windows[i] for i in ind]
    #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    #window_img = vehicleUtil.draw_boxes(img, hot_windows, color=(0, 0, 255), thick=6) 

    # Add heat to each box in box list
    heat = vehicleUtil.add_heat(heat,hot_windows)
    # Apply threshold to help remove false positives for current frame
    heat = vehicleUtil.apply_threshold(heat,1)
    heatmap_arr.append(heat)
    if len(heatmap_arr) > heatmap_filterSize:
        heatmap_arr = heatmap_arr[1:]
    heat_combined = np.zeros_like(img[:,:,0]).astype(np.float)
    for i in range(len(heatmap_arr)):
        heat_combined = heat_combined + heatmap_arr[i]
    heat_combined = vehicleUtil.apply_threshold(heat_combined,4)
    # Visualize the heatmap when displaying    
    heatmap = np.clip(heat_combined, 0, 255)
    labels = label(heatmap)
    return heatmap, labels, hot_windows


def process_vidFrame(img):
    global frame_i
    frame_i += 1
    #img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    heatmap, labels, hot_windows = process_frame_efficient(img)
    label_img = vehicleUtil.draw_labeled_bboxes(np.copy(img), labels)
    if outputDebug:
        imgSize = (720, 1280 , 3)
        out_img = np.zeros(imgSize, dtype=np.uint8)

        smallFinal = cv2.resize(label_img, (0,0), fx=0.5, fy=0.5)
        smallFinalSize = (smallFinal.shape[1], smallFinal.shape[0])
        out_img[0:smallFinalSize[1], 0:smallFinalSize[0]] = smallFinal

        heatmap = heatmap*(255/8)
        heatmap = np.clip(heatmap, 0, 255)
        heatmap = np.dstack((heatmap, heatmap, heatmap))
        smallHeat = cv2.resize(heatmap, (0,0), fx=0.5, fy=0.5)
        smallHeatSize = (smallHeat.shape[1], smallHeat.shape[0])
        out_img[0:smallHeatSize[1], smallFinalSize[0]:smallFinalSize[0]+smallHeatSize[0]] = smallHeat

        window_img = vehicleUtil.draw_boxes(img, hot_windows, color=(0, 0, 255), thick=6)
        rawWindows = cv2.resize(window_img, (0,0), fx=0.5, fy=0.5)
        rawWindowsSize = (rawWindows.shape[1], rawWindows.shape[0])
        out_img[smallFinalSize[1]:smallFinalSize[1]+rawWindowsSize[1], smallFinalSize[0]:smallFinalSize[0]+rawWindowsSize[0]] = rawWindows
    else:
        window_img = vehicleUtil.draw_boxes(img, hot_windows, color=(0, 0, 255), thick=6)
        out_img = vehicleUtil.convertClrSpace(window_img, 'RGB')
    if rawOutput:
        blankImg = cv2.zeros_like(img)
        cv2.imwrite('rawOut/img_{0:0>4}.jpg'.format(frame_i), vehicleUtil.draw_boxes(img, hot_windows, color=(0, 0, 255), thick=6))
    return out_img


def main():
    global method
    global model
    global frame_i
    frame_i = 0
    method = sys.argv[1]
    if method == 'cnn':
        from keras.models import load_model
        from keras import backend as K
        model = load_model(cnn_model)
    file = sys.argv[2]
    if file.endswith('.jpg'):
        img = cv2.imread(file)
        img = vehicleUtil.convertClrSpace(img, colorspace='RGB')
        heatmap, labels, hot_windows = process_frame_efficient(img, debug=True)
        label_img = vehicleUtil.draw_labeled_bboxes(np.copy(img), labels)
        #label_img = vehicleUtil.convertClrSpace(label_img, colorspace='RGB')
        hotWindows_img = vehicleUtil.draw_boxes(img, hot_windows, color=(0, 0, 255), thick=6)
        fig = plt.figure()
        plt.subplot(131)
        plt.imshow(hotWindows_img)
        plt.title('Hot Windows')
        plt.subplot(132)
        plt.imshow(heatmap, cmap='hot')
        plt.title('Heat Map')
        plt.subplot(133)
        plt.imshow(label_img)
        plt.title('Car Positions')
        fig.tight_layout()
        plt.show()
    else:
        # through low contrast and some shadows
        #clip = VideoFileClip(file).subclip('00:00:13.00','00:00:27.00')
        # lots of shadows
        #clip = VideoFileClip(file).subclip('00:00:40.00','00:00:42.00')
        clip = VideoFileClip(file)

        proc_clip = clip.fl_image(process_vidFrame)
        if method == 'svm':
            proc_output = '{}_proc.mp4'.format(file.split('.')[0])
        else:
            proc_output = '{}_proc_cnn.mp4'.format(file.split('.')[0])
        proc_clip.write_videofile(proc_output, audio=False)
    if method == 'cnn':
        K.clear_session() #otherwise it often errors out here. Some python/keras garbage collection issue.
    

if __name__ == '__main__':
    main()

