'''
This is for inference only, with the pre-trianed model weights in the same folder
'''

import sys
import random
import os
import warnings
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from itertools import chain
from tensorflow.keras import layers
from tensorflow.keras import losses
from tensorflow.keras import models
from tensorflow.keras import callbacks
import tensorflow.keras.backend as K
from tensorflow import keras
import glob
# from PIL import Image
import glob
import tensorflow as tf
import time
import cv2

print(tf.__version__)
print(np.__version__)
print(cv2.__version__)

gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    print("Name:", gpu.name, "  Type:", gpu.device_type)

IMG_WIDTH = 512
IMG_HEIGHT = 512
IMG_CHANNELS = 3
TRAIN_NUM = 1700
TEST_NUM = 300
sample_dir = "../NewDataset/train/img/"
mask_dir = "../NewDataset/train/mask/"
test_sample_dir = "../dataset_kaggle/testing/sample/"
test_mask_dir = "../dataset_kaggle/testing/mask/"
# MODEL_PATH = "./kaggle_myIOU_weights.hdf5"ask/"
MODEL_PATH = "./local_weights.hdf5"

# Get the filenames of training and testing data
sample_ids = next(os.walk(sample_dir))[2]
test_sample_ids = next(os.walk(test_sample_dir))[2]
print(sample_ids[:10])
print(test_sample_ids[:10])

batch_size = 8
class DataGenerator(tf.keras.utils.Sequence):
    #     'Generates data for Keras'
    def __init__(self, train_im_path=sample_dir, train_mask_path=mask_dir,
                 augmentations=None, batch_size=batch_size, img_size=512, n_channels=3, shuffle=True, mode="train"):
        #         'Initialization'
        self.batch_size = batch_size
        self.train_im_paths = glob.glob(train_im_path + '*')
        print("The train_im_paths fetched by the program is:")
        print(self.train_im_paths[:10])

        self.train_im_path = train_im_path
        self.train_mask_path = train_mask_path

        self.img_size = img_size

        self.n_channels = n_channels
        self.shuffle = shuffle
        # No augmentation is needed for inference only applications
        self.augment = augmentations
        self.mode = mode
        self.on_epoch_end()

    def __len__(self):
        #         'Denotes the number of batches per epoch'
        return int(np.ceil(len(self.train_im_paths) / self.batch_size))

    def __getitem__(self, index):

        # Generate indexes of the batch
        indexes = self.indexes[index * self.batch_size:min((index + 1) * self.batch_size, len(self.train_im_paths))]

        # Find list of IDs
        list_IDs_im = [self.train_im_paths[k] for k in indexes]

        # Generate data
        X, y = self.data_generation(list_IDs_im)
        # First generate data, 0 < Image[i,j] < 255
        # Then rescale them,  0 < Image[i,j] < 1

        if self.augment is None:
            return X.astype(np.float32) / 255, np.array(y).astype(np.float32) / 255
        else:
            print("Error: This program does not allow augmentations")

    def on_epoch_end(self):
        'Updates indexes after each epoch'
        self.indexes = np.arange(len(self.train_im_paths))
        if self.shuffle == True:
            np.random.shuffle(self.indexes)

    def data_generation(self, list_IDs_im):
        'Generates data containing batch_size samples'
        # X : (n_samples, *dim, n_channels)
        # Initialization
        X = np.empty((len(list_IDs_im), self.img_size, self.img_size, self.n_channels))
        y = np.empty((len(list_IDs_im), self.img_size, self.img_size, 1))

        # Generate data
        for i, im_path in enumerate(list_IDs_im):

            # print("---------")
            # print(im_path)
            # print(self.train_im_path)
            # print(self.train_mask_path)
            # print("-----------")

            im = cv2.imread(im_path)
            im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
            mask_path = im_path.replace(self.train_im_path[:-1], self.train_mask_path[:-1])

            if self.mode == "train":
                pass
            else:
                mask_path = mask_path[:-4] + "_matte.png"

            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if len(im.shape) == 2:
                print("shape before:", im.shape)
                im = np.repeat(im[..., None], 3, 2)
                print("shape after:", im.shape)

            # Resize sample
            X[i,] = cv2.resize(im, (self.img_size, self.img_size))
            y[i,] = cv2.resize(mask, (self.img_size, self.img_size))[..., np.newaxis]

            # USING cv2.resize(), the values are between 0 and 255
            y[y > 64] = 255
            y[y < 64] = 0

        return X, y

'''
Test to see the image generator is working properly'''
a = DataGenerator(batch_size=2, shuffle=False)
gen_images,gen_masks = a.__getitem__(0)
print(len(gen_images))
print(len(gen_masks))


# for i in range(2):
#     img = gen_images[i]
#     gt = gen_masks[i]
#     plt.imshow(img)
#
#     plt.show()
#     plt.imshow(gt.squeeze(), cmap = "Greys")
#
#     plt.show()

'''
Load the model directly from hdf5 file
'''


def dice_coeff(y_true, y_pred):
    smooth = 1.
    # Flatten
    y_true_f = tf.reshape(y_true, [-1])
    y_pred_f = tf.reshape(y_pred, [-1])
    intersection = tf.reduce_sum(y_true_f * y_pred_f)
    score = (2. * intersection + smooth) / (tf.reduce_sum(y_true_f) + tf.reduce_sum(y_pred_f) + smooth)
    return score


def dice_loss(y_true, y_pred):
    loss = 1 - dice_coeff(y_true, y_pred)
    return loss


def bce_dice_loss(y_true, y_pred):
    loss = losses.binary_crossentropy(y_true, y_pred) + dice_loss(y_true, y_pred)
    return loss


def myIOU(y_true, y_pred):
    smooth = 0.001
    intersection = K.sum(K.abs(y_true * y_pred), axis=-1)
    union = K.sum(y_true, -1) + K.sum(y_pred, -1) - intersection
    return (intersection + smooth) / (union + smooth)

myModel = keras.models.load_model(MODEL_PATH, custom_objects={'bce_dice_loss': bce_dice_loss,
                                                           'dice_loss': dice_loss, 'myIOU':myIOU})
myModel.summary()

# Here the two generators are instantiated to fit in the model.fit_generator()
batchSize = 4
print(sample_dir)
print(mask_dir)
print(test_sample_dir)
print(test_mask_dir)

training_generator = DataGenerator(batch_size= batchSize,
                                   augmentations = None,
                                   img_size=IMG_HEIGHT, #512 x 512
                                   mode = "train")

validation_generator = DataGenerator(batch_size=batchSize,
                                     train_im_path = test_sample_dir,
                                     train_mask_path=test_mask_dir,
                                     augmentations=None,
                                     img_size=IMG_HEIGHT, #512 x 512
                                     mode = "test")

save_model_path = './local_weights.hdf5'
cp = tf.keras.callbacks.ModelCheckpoint(filepath=save_model_path, monitor='val_loss', save_best_only=True, verbose=1)
#
# history = myModel.fit_generator(training_generator,
#                     epochs=1,
#                     validation_data = validation_generator,
#                     callbacks=[cp],
#                     verbose =1,
#                     workers=8
#                     )

# test_generator = DataGenerator(batch_size=1,train_im_path = test_sample_dir ,
#                                      train_mask_path=test_mask_dir,
#                                      augmentations=None,
#                                      img_size=IMG_HEIGHT,
#                                     shuffle= True,
#                                     mode = "test")
#
# print("started infering")
# # Now visualize 5 predictions made by the model
# fig, axes = plt.subplots(3,5)
#
# for i in range(1,6): # from 1 to 12
#     test_img, test_mask = test_generator.__getitem__(i-1)
#     # print(test_img.shape)
#     # print(test_mask.shape)
#     predicted_mask = myModel.predict(test_img)
#
#     test_img = test_img[0]
#     test_mask = test_mask[0]
#     predicted_mask = predicted_mask[0]
#
#     axes[0,i-1].imshow(test_img)
#     axes[1, i-1].imshow(test_mask.squeeze(), cmap="Greys")
#     axes[2, i-1].imshow(predicted_mask.squeeze(), cmap="Greys")
#
# plt.show()


'''
The above code has shown the model's working correctly.
Now use integrate opencv into the production, feeding the model with direct frames
'''


vidCap = cv2.VideoCapture(0)
frame_count = 0
# Create a batch of size 1 to hold every single frame
images = np.zeros((1, IMG_HEIGHT, IMG_WIDTH, IMG_CHANNELS))
while True:
    frame_count += 1
    ret, img = vidCap.read() #ret ==> boolean flag for successfully capture or not; img ==> a still frame captured
    if not ret:
        print("fails to access your camera")
        break

    # horizontally flip this image
    img = img[:,::-1,:]
    img = cv2.resize(img, (IMG_HEIGHT, IMG_WIDTH))

    #Pre-process this image
    input_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    input_img = cv2.resize(input_img, (IMG_HEIGHT, IMG_WIDTH))
    input_img = input_img/255.
    images[0] = input_img

    #Now feed in this mini-batch with only 1 image inside
    mask = myModel.predict(images)
    mask = mask[0] # reduce output dimensions

    #Threshold this mask
    mask[mask>0.8] = 1
    mask[mask <= 0.8] = 0
    mask = mask.astype(np.uint8)

    # mask = cv2.adaptiveThreshold(mask*255, 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 180, 1)
    print(mask.shape)
    print(img.shape)
    img = cv2.bitwise_and(img, img, mask = mask)


    cv2.imshow("VideoStreaming", img)
    stopKey = cv2.waitKey(12)
    keyChar = chr(stopKey & 0xff)

    if keyChar == "q":
        break
    elif keyChar == "s":
        cv2.imwrite("snapshot.jpg", img[:,::-1,:])

cv2.destroyAllWindows()
vidCap.release()


print(frame_count)
