'''
训练svm
'''

import cv2
import numpy as np
from numpy.linalg import norm
import os
from sklearn.model_selection import GridSearchCV
from joblib import Parallel, delayed


SZ = 20
PROVINCE_START = 1000

provinces = [
"zh_cuan", "川",
"zh_e", "鄂",
"zh_gan", "赣",
"zh_gan1", "甘",
"zh_gui", "贵",
"zh_gui1", "桂",
"zh_hei", "黑",
"zh_hu", "沪",
"zh_ji", "冀",
"zh_jin", "津",
"zh_jing", "京",
"zh_jl", "吉",
"zh_liao", "辽",
"zh_lu", "鲁",
"zh_meng", "蒙",
"zh_min", "闽",
"zh_ning", "宁",
"zh_qing", "靑",
"zh_qiong", "琼",
"zh_shan", "陕",
"zh_su", "苏",
"zh_sx", "晋",
"zh_wan", "皖",
"zh_xiang", "湘",
"zh_xin", "新",
"zh_yu", "豫",
"zh_yu1", "渝",
"zh_yue", "粤",
"zh_yun", "云",
"zh_zang", "藏",
"zh_zhe", "浙"
]


# 数据处理
def deskew(img):
	m = cv2.moments(img)
	if abs(m['mu02']) < 1e-2:
		return img.copy()
	skew = m['mu11']/m['mu02']
	M = np.float32([[1, skew, -0.5*SZ*skew], [0, 1, 0]])
	img = cv2.warpAffine(img, M, (SZ, SZ), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR)
	return img

# 特征工程
def preprocess_hog(digits):
	samples = []
	for img in digits:
		gx = cv2.Sobel(img, cv2.CV_32F, 1, 0)
		gy = cv2.Sobel(img, cv2.CV_32F, 0, 1)
		mag, ang = cv2.cartToPolar(gx, gy)
		bin_n = 16
		bin = np.int32(bin_n*ang/(2*np.pi))
		bin_cells = bin[:10,:10], bin[10:,:10], bin[:10,10:], bin[10:,10:]
		mag_cells = mag[:10,:10], mag[10:,:10], mag[:10,10:], mag[10:,10:]
		hists = [np.bincount(b.ravel(), m.ravel(), bin_n) for b, m in zip(bin_cells, mag_cells)]
		hist = np.hstack(hists)

		# transform to Hellinger kernel
		eps = 1e-7
		hist /= hist.sum() + eps
		hist = np.sqrt(hist)
		hist /= norm(hist) + eps

		samples.append(hist)
	return np.float32(samples)

#通过对输入图像进行旋转和缩放，augment_image 函数生成了多个变换版本的图像，这些增强图像可以用于训练机器学习模型。这样的数据增强技术有助于提升模型的泛化能力
def augment_image(img):
	# Data augmentation: Rotate, Scale, and Translate
	augmentations = []
	for angle in [0, 15, -15]:  # Add rotation
		M = cv2.getRotationMatrix2D((SZ / 2, SZ / 2), angle, 1)
		rotated = cv2.warpAffine(img, M, (SZ, SZ))
		augmentations.append(rotated)

	for scale in [0.8, 1.2]:  # Add scaling
		scaled = cv2.resize(img, None, fx=scale, fy=scale)
		scaled_cropped = cv2.resize(scaled, (SZ, SZ))
		augmentations.append(scaled_cropped)

	return augmentations

class StatModel(object):
	def load(self, fn):
		self.model = self.model.load(fn)
	def save(self, fn):
		self.model.save(fn)

class SVM(StatModel):
	def __init__(self, C = 1, gamma = 0.5):
		self.model = cv2.ml.SVM_create()
		self.model.setGamma(gamma)
		self.model.setC(C)
		self.model.setKernel(cv2.ml.SVM_RBF)
		self.model.setType(cv2.ml.SVM_C_SVC)
	# train svm
	def train(self, samples, responses):
		self.model.train(samples, cv2.ml.ROW_SAMPLE, responses)
	# inference
	def predict(self, samples):
		r = self.model.predict(samples)
		return r[1].ravel()

	def train_svm(self):
		#识别英文字母和数字
		self.model = SVM(C=1, gamma=0.5)
		#识别中文
		self.modelchinese = SVM(C=1, gamma=0.5)
		if os.path.exists("./train_dat/svm1.dat"):
			self.model.load("./train_dat/svm1.dat")
		else:
			chars_train = []
			chars_label = []
			#directory = "D:\\综合\\学习\\企业实训\\project\\license-plate-recognition-master\\train\\chars2"
			for root, dirs, files in os.walk("train\\chars2"):
				if len(os.path.basename(root)) > 1:
					continue
				root_int = ord(os.path.basename(root))
				for filename in files:
					filepath = os.path.join(root,filename)
					digit_img = cv2.imread(filepath)
					if digit_img is None:
						print(f"Failed to read image: {filepath}")  # 打印未能读取的文件
						continue  # 跳过未读取的图像
					digit_img = cv2.cvtColor(digit_img, cv2.COLOR_BGR2GRAY)
					chars_train.append(digit_img)
					#chars_label.append(1)
					chars_label.append(root_int)

			chars_train = list(map(deskew, chars_train))
			chars_train = preprocess_hog(chars_train)
			#chars_train = chars_train.reshape(-1, 20, 20).astype(np.float32)
			chars_label = np.array(chars_label)
			print(chars_train.shape)
			self.model.train(chars_train, chars_label)
			# 调试信息
			print(f"chars_train shape after processing: {np.array(chars_train).shape}")
			print(f"chars_label shape: {chars_label.shape}")

			if len(chars_train) == 0:
				print("No valid training images found.")
			else:
				self.model.train(chars_train, chars_label)

        # Load Chinese characters
		if os.path.exists("./train_dat/svmchinese1.dat"):
			self.modelchinese.load("./train_dat/svmchinese1.dat")
		else:
			chars_train = []
			chars_label = []
			for root, dirs, files in os.walk("train\\charsChinese"):
				if not os.path.basename(root).startswith("zh_"):
					continue
				pinyin = os.path.basename(root)
				index = provinces.index(pinyin) + PROVINCE_START + 1 #1是拼音对应的汉字
				augmented_images = Parallel(n_jobs=-1)(
					delayed(augment_image)(cv2.imread(os.path.join(root, filename)))
					for filename in files
				)
				for images in augmented_images:
					for img in images:
						img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
						chars_train.append(img)
						chars_label.append(index)
				"""for filename in files:
					filepath = os.path.join(root,filename)
					digit_img = cv2.imread(filepath)
					digit_img = cv2.cvtColor(digit_img, cv2.COLOR_BGR2GRAY)
					chars_train.append(digit_img)
					#chars_label.append(1)
					chars_label.append(index)"""
			chars_train = list(map(deskew, chars_train))
			chars_train = preprocess_hog(chars_train)
			#chars_train = chars_train.reshape(-1, 20, 20).astype(np.float32)
			chars_label = np.array(chars_label)
			print(chars_train.shape)
			self.modelchinese.train(chars_train, chars_label)
			self.save_traindata()

		return self.model, self.modelchinese

	def save_traindata(self):
		if not os.path.exists("./train_dat/svm1.dat"):
			print("svm1保存成功!!!")
			self.model.save("./train_dat/svm1.dat")
		if not os.path.exists("./train_dat/svmchinese1.dat"):
			print("svmchinese1保存成功!!!")
			self.modelchinese.save("./train_dat/svmchinese1.dat")



	