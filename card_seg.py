from car_id_detect import *
from svm_train import *

SZ = 20          # 训练图片长宽
MAX_WIDTH = 1000 # 原始图片最大宽度
Min_Area = 2000  # 车牌区域允许最大面积
PROVINCE_START = 1000

svm_model = SVM(C=1, gamma=0.5)
model_1, model_2 = svm_model.train_svm()

def find_waves(threshold, histogram):
    '''
    根据设定的阈值和图片直方图，找出波峰，用于分隔字符
    '''
    up_point = -1 # 上升点
    is_peak = False
    if histogram[0] > threshold:
        up_point = 0
        is_peak = True
    wave_peaks = []
    for i, x in enumerate(histogram):
        if is_peak and x < threshold:
            if i - up_point > 2:
                is_peak = False
                wave_peaks.append((up_point, i))
        elif not is_peak and x >= threshold:
            is_peak = True
            up_point = i
    if is_peak and up_point != -1 and i - up_point > 4:
        wave_peaks.append((up_point, i))
    return wave_peaks

def seperate_card(img, waves):
    '''
    根据找出的波峰，分隔图片，从而得到逐个字符图片
    '''
    part_cards = []
    for wave in waves:
        part_cards.append(img[:, wave[0]:wave[1]])
    return part_cards

def Cardseg(rois, colors):
    '''
    把一个roi列表和color列表，对应的每个车牌分割成一个一个的字
    然后做预测分类

    当然也可以考虑OCR的办法，这里使用的是传统的分类问题解决的
    '''
    sign, seg_dic, old_seg_dic, predict_result = 0, 0, 0, 0
    seg_dic = {}
    old_seg_dic = {}
    for i, color in enumerate(colors):
        if color in ("blue", "yello", "green"):
            # 打印当前车牌颜色
            print(f"处理的车牌颜色是: {color}")
            card_img = rois[i]
            # 显示整个车牌区域
            cv2.imshow(f"车牌{i + 1} 区域", card_img)  # 显示车牌区域
            cv2.waitKey(0)  # 等待按键
            cv2.destroyAllWindows()  # 销毁窗口
            gray_img = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
            # 黄、绿车牌字符比背景暗，与蓝车牌相反，因此黄、绿车牌需要反向
            if color == "green" or color == "yello":
                gray_img = cv2.bitwise_not(gray_img)
            ret, gray_img = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # 查找水平直方图波峰
            x_histogram = np.sum(gray_img, axis=1)
            x_min = np.min(x_histogram)
            x_average = np.sum(x_histogram) / x_histogram.shape[0]
            x_threshold = (x_min + x_average) / 2
            wave_peaks = find_waves(x_threshold, x_histogram)
            if len(wave_peaks) == 0:
                continue

            wave = max(wave_peaks, key=lambda x: x[1] - x[0])
            gray_img = gray_img[wave[0]:wave[1]]

            # 查找垂直直方图波峰
            row_num, col_num = gray_img.shape[:2]
            gray_img = gray_img[1:row_num - 1]
            y_histogram = np.sum(gray_img, axis=0)
            y_min = np.min(y_histogram)
            y_average = np.sum(y_histogram) / y_histogram.shape[0]
            y_threshold = (y_min + y_average) / 5

            wave_peaks = find_waves(y_threshold, y_histogram)

            if len(wave_peaks) <= 6:
                continue
            wave = max(wave_peaks, key=lambda x: x[1] - x[0])
            max_wave_dis = wave[1] - wave[0]

            if wave_peaks[0][1] - wave_peaks[0][0] < max_wave_dis / 3 and wave_peaks[0][0] == 0:
                wave_peaks.pop(0)

            cur_dis = 0
            for i, wave in enumerate(wave_peaks):
                if wave[1] - wave[0] + cur_dis > max_wave_dis * 0.6:
                    break
                else:
                    cur_dis += wave[1] - wave[0]
            if i > 0:
                wave = (wave_peaks[0][0], wave_peaks[i][1])
                wave_peaks = wave_peaks[i + 1:]
                wave_peaks.insert(0, wave)

            point = wave_peaks[2]
            if point[1] - point[0] < max_wave_dis / 3:
                point_img = gray_img[:, point[0]:point[1]]
                if np.mean(point_img) < 255 / 5:
                    wave_peaks.pop(2)

            if len(wave_peaks) <= 6:
                continue
            part_cards = seperate_card(gray_img, wave_peaks)

            predict_result = []
            for i, part_card in enumerate(part_cards):
                if np.mean(part_card) < 255 / 5:
                    continue
                part_card_old = part_card
                w = abs(part_card.shape[1] - SZ) // 2
                part_card = cv2.copyMakeBorder(part_card, 0, 0, w, w, cv2.BORDER_CONSTANT, value=[0, 0, 0])
                part_card = cv2.resize(part_card, (SZ, SZ), interpolation=cv2.INTER_AREA)

                part_card = preprocess_hog([part_card])
                if i == 0:
                    resp = model_2.predict(part_card)
                    charactor = provinces[int(resp[0]) - PROVINCE_START]  # 将 resp[0] 转为整数
                else:
                    resp = model_1.predict(part_card)
                    charactor = chr(int(resp[0]))  # 将 resp[0] 转为整数
                if charactor == "1" and i == len(part_cards) - 1:
                    if part_card_old.shape[0] / part_card_old.shape[1] >= 7:
                        continue
                predict_result.append(charactor)

            sign = 1
            seg_dic[i] = part_cards
            old_seg_dic[i] = part_card_old
    return sign, seg_dic, old_seg_dic, predict_result
