import cv2 
import mediapipe as mp
import math
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np 
import pygame
import time
from datetime import datetime
import os 
import torch

pygame.init()
alarm = pygame.mixer.Sound("sound files/short alarm.mp3")


def distance(p1, p2):
    ''' Calculate distance between two points
    :param p1: First Point 
    :param p2: Second Point
    :return: Euclidean distance between the points. (Using only the x and y coordinates).
    '''
    return (((p1[:2] - p2[:2])**2).sum())**0.5

def eye_aspect_ratio(landmarks, eye):
    ''' Calculate the ratio of the eye length to eye width. 
    :param landmarks: Face Landmarks returned from FaceMesh MediaPipe model
    :param eye: List containing positions which correspond to the eye
    :return: Eye aspect ratio value
    '''
    N1 = distance(landmarks[eye[1][0]], landmarks[eye[1][1]])
    N2 = distance(landmarks[eye[2][0]], landmarks[eye[2][1]])
    N3 = distance(landmarks[eye[3][0]], landmarks[eye[3][1]])
    D = distance(landmarks[eye[0][0]], landmarks[eye[0][1]])
    return (N1 + N2 + N3) / (3 * D)

def eye_feature(landmarks):
    ''' Calculate the eye feature as the average of the eye aspect ratio for the two eyes
    :param landmarks: Face Landmarks returned from FaceMesh MediaPipe model
    :return: Eye feature value
    '''
    return (eye_aspect_ratio(landmarks, left_eye) + \
    eye_aspect_ratio(landmarks, right_eye))/2

def mouth_feature(landmarks):
    ''' Calculate mouth feature as the ratio of the mouth length to mouth width
    :param landmarks: Face Landmarks returned from FaceMesh MediaPipe model
    :return: Mouth feature value
    '''
    N1 = distance(landmarks[mouth[1][0]], landmarks[mouth[1][1]])
    N2 = distance(landmarks[mouth[2][0]], landmarks[mouth[2][1]])
    N3 = distance(landmarks[mouth[3][0]], landmarks[mouth[3][1]])
    D = distance(landmarks[mouth[0][0]], landmarks[mouth[0][1]])
    return (N1 + N2 + N3)/(3*D)

def pupil_circularity(landmarks, eye):
    ''' Calculate pupil circularity feature.
    :param landmarks: Face Landmarks returned from FaceMesh MediaPipe model
    :param eye: List containing positions which correspond to the eye
    :return: Pupil circularity for the eye coordinates
    '''
    perimeter = distance(landmarks[eye[0][0]], landmarks[eye[1][0]]) + \
            distance(landmarks[eye[1][0]], landmarks[eye[2][0]]) + \
            distance(landmarks[eye[2][0]], landmarks[eye[3][0]]) + \
            distance(landmarks[eye[3][0]], landmarks[eye[0][1]]) + \
            distance(landmarks[eye[0][1]], landmarks[eye[3][1]]) + \
            distance(landmarks[eye[3][1]], landmarks[eye[2][1]]) + \
            distance(landmarks[eye[2][1]], landmarks[eye[1][1]]) + \
            distance(landmarks[eye[1][1]], landmarks[eye[0][0]])
    area = math.pi * ((distance(landmarks[eye[1][0]], landmarks[eye[3][1]]) * 0.5) ** 2)
    return (4*math.pi*area)/(perimeter**2)

def pupil_feature(landmarks):
    ''' Calculate the pupil feature as the average of the pupil circularity for the two eyes
    :param landmarks: Face Landmarks returned from FaceMesh MediaPipe model
    :return: Pupil feature value
    '''
    return (pupil_circularity(landmarks, left_eye) + \
        pupil_circularity(landmarks, right_eye))/2

def run_face_mp(image):
    ''' Get face landmarks using the FaceMesh MediaPipe model. 
    Calculate facial features using the landmarks.
    :param image: Image for which to get the face landmarks
    :return: Feature 1 (Eye), Feature 2 (Mouth), Feature 3 (Pupil), \
        Feature 4 (Combined eye and mouth feature), image with mesh drawings
    '''
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = face_mesh.process(image)
    
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    if results.multi_face_landmarks:
        landmarks_positions = []
        # assume that only face is present in the image
        for _, data_point in enumerate(results.multi_face_landmarks[0].landmark):
            landmarks_positions.append([data_point.x, data_point.y, data_point.z]) # saving normalized landmark positions
        landmarks_positions = np.array(landmarks_positions)
        landmarks_positions[:, 0] *= image.shape[1]
        landmarks_positions[:, 1] *= image.shape[0]

        # draw face mesh over image
        for face_landmarks in results.multi_face_landmarks:
            mp_drawing.draw_landmarks(
                image=image,
                landmark_list=face_landmarks,
                landmark_drawing_spec=drawing_spec,
            )

        ear = eye_feature(landmarks_positions)
        mar = mouth_feature(landmarks_positions)
        puc = pupil_feature(landmarks_positions)
        moe = mar / ear
    else:
        cv2.putText(image, "NO FACE DETECTED", (int(0.02*image.shape[1]), int(0.1*image.shape[0])),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        ear = -1000
        mar = -1000
        puc = -1000
        moe = -1000

    return ear, mar, puc, moe, image

def calibrate(calib_frame_count=120):
    ''' Perform clibration. Get features for the neutral position.
    :param calib_frame_count: Image frames for which calibration is performed. Default Vale of 120.
    :return: Normalization Values for feature 1, Normalization Values for feature 2, \
        Normalization Values for feature 3, Normalization Values for feature 4
    '''
    ears = []
    mars = []
    pucs = []
    moes = []

    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            continue

        ear, mar,puc, moe, image = run_face_mp(image)
        if ear != -1000:
            ears.append(ear)
            mars.append(mar)
            pucs.append(puc)
            moes.append(moe)

        cv2.putText(image, "Calibration", (int(0.02*image.shape[1]), int(0.14*image.shape[0])),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 2)
        cv2.imshow('Calibration Frame', image)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break
        if len(ears) >= calib_frame_count:
            break
    
    cv2.destroyAllWindows()
    cap.release()
    ears = np.array(ears)
    mars = np.array(mars)
    pucs = np.array(pucs)
    moes = np.array(moes)
    return [ears.mean(), ears.std()], [mars.mean(), mars.std()], \
        [pucs.mean(), pucs.std()], [moes.mean(), moes.std()]

def get_classification(input_data):
    ''' Perform classification over the facial  features.
    :param input_data: List of facial features for 20 frames
    :return: Alert / Drowsy state prediction
    '''
    model_input = []
    model_input.append(input_data[:5])
    model_input.append(input_data[3:8])
    model_input.append(input_data[6:11])
    model_input.append(input_data[9:14])
    model_input.append(input_data[12:17])
    model_input.append(input_data[15:])
    model_input = torch.FloatTensor(np.array(model_input))
    preds = torch.sigmoid(model(model_input)).gt(0.5).int().data.numpy()
    return int(preds.sum() >= 5)

def infer(ears_norm, mars_norm, pucs_norm, moes_norm):
    df = pd.DataFrame(columns=['ear_main', 'mar_main', 'time'])
    ''' Perform inference.
    :param ears_norm: Normalization values for eye feature
    :param mars_norm: Normalization values for mouth feature
    :param pucs_norm: Normalization values for pupil feature
    :param moes_norm: Normalization values for mouth over eye feature. 
    '''
    ear_main = 0
    mar_main = 0
    puc_main = 0
    moe_main = 0
    decay = 0.9 # use decay to smoothen the noise in feature values

    label = None

    input_data = []
    frame_before_run = 0

    cap = cv2.VideoCapture(0)
    start_time = time.time()
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            continue

        ear, mar, puc, moe, image = run_face_mp(image)
        if ear != -1000:
            ear = (ear - ears_norm[0])/ears_norm[1]
            mar = (mar - mars_norm[0])/mars_norm[1]
            puc = (puc - pucs_norm[0])/pucs_norm[1]
            moe = (moe - moes_norm[0])/moes_norm[1]
            if ear_main == -1000:
                ear_main = ear
                mar_main = mar
                puc_main = puc
                moe_main = moe
            else:
                ear_main = ear_main*decay + (1-decay)*ear
                mar_main = mar_main*decay + (1-decay)*mar
                puc_main = puc_main*decay + (1-decay)*puc
                moe_main = moe_main*decay + (1-decay)*moe
        else:
            ear_main = -1000
            mar_main = -1000
            puc_main = -1000
            moe_main = -1000
            
        # append data into the dataframe
        current_time = time.time()
        elapsed_time = current_time - start_time

        # Add data to dataframe every second
        if int(elapsed_time) > len(df):
            df = pd.concat([df, pd.DataFrame({'ear_main': [ear_main], 'mar_main': [mar_main], 'time': [datetime.now()]})], ignore_index=True)
        
        if len(input_data) == 20:
            input_data.pop(0)
        input_data.append([ear_main, mar_main, puc_main, moe_main])

        frame_before_run += 1
        if frame_before_run >= 15 and len(input_data) == 20 and ear != -1000 and mar != -1000 and puc != -1000 and moe != -1000:
            frame_before_run = 0
            label = get_classification(input_data)
            print ('Output label ', label)
        
        cv2.putText(image, "EAR: %.2f" %(ear_main), (int(0.20*image.shape[1]), int(0.07*image.shape[0])),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(image, "MAR: %.2f" %(mar_main), (int(0.60*image.shape[1]), int(0.07*image.shape[0])),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        if label is not None:
            if label == 0:
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
                alarm_time = datetime.now()
                alarm.set_volume(0.5)
                alarm.play()
            cv2.putText(image, "%s" %(states[label]), (int(0.02*image.shape[1]), int(0.2*image.shape[0])),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 2)



        cv2.imshow('MediaPipe FaceMesh', image)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break
    
    cv2.destroyAllWindows()
    cap.release()
    print(df)
    df.to_csv('facial_data.csv', index=False)
    data = pd.read_csv('facial_data.csv')
    data['rounded_ear'] = data['ear_main'].apply(lambda x: round(x,1))
    data['rounded_mar'] = data['mar_main'].apply(lambda x: round(x,1))
    data['time'] = pd.to_datetime(data['time'])

    fig, ax = plt.subplots(figsize=(7,5))
    
    ax.set_ylim(-10, 10)
    # Plot ear_main against time with seconds
    ax.plot(data['time'], data['rounded_ear'], linestyle='-', linewidth=0.5, color='red', label='EAR')
    ax.plot(data['time'], data['rounded_mar'], linestyle='-', linewidth=0.5, color='blue', label='MAR')


    # Format x-axis to show minutes with seconds
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))

    # Set x-axis locator to every second
    ax.xaxis.set_major_locator(mdates.SecondLocator(interval=10))

    # You might want to adjust the labels and title accordingly
    ax.set_xlabel('Time (Minutes:Seconds)')
    ax.set_ylabel('EAR/MAR')
    ax.set_title('EAR and MAR over Time')
    ax.legend()
    plt.xticks(rotation=70)  
    plt.tight_layout()  
    
    min_ear_time = data[data['ear_main'] == data['ear_main'].min()]['time']
    hour_minute = min_ear_time.dt.strftime('%H:%M').values[0]
    
    min_ear_time = data[data['ear_main'] == data['ear_main'].max()]['time']
    hour_minutes = min_ear_time.dt.strftime('%H:%M').values[0]
    print(ears_norm[0])
    print(mars_norm[0])
    list_lenght = []
    for i in (data['ear_main']).tolist():
        if i < ears_norm[0]:
            list_lenght.append(i)
    
    # Add text beside the plot
    text = f'''
    CALIBERATED EYE ASPECT RATIO: 
    {round(ears_norm[0],2)}
    
    CALIBERATED MOUTH ASPECT RATIO: 
    {round(mars_norm[0],2)}
    
    You felt the most sleepy at {hour_minute}
    You felt most awake at {hour_minutes}
    Number of times you felt drowsy: {len(list_lenght)}
        '''
    plt.text(1.01, 0.2, text, transform=ax.transAxes, verticalalignment='bottom', fontsize=8)
    plt.savefig('fig1.jpg')
    plt.show()


right_eye = [[33, 133], [160, 144], [159, 145], [158, 153]] # right eye landmark positions
left_eye = [[263, 362], [387, 373], [386, 374], [385, 380]] # left eye landmark positions
mouth = [[61, 291], [39, 181], [0, 17], [269, 405]] # mouth landmark coordinates
states = ['ALERT', 'DROWSY']

# Declaring FaceMesh model
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    min_detection_confidence=0.3, min_tracking_confidence=0.8)
mp_drawing = mp.solutions.drawing_utils 
drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

model_lstm_path = 'clf_lstm_jit6.pth'
model = torch.jit.load(model_lstm_path)
model.eval()

print ('Starting calibration. Please be in neutral state')
time.sleep(1)
ears_norm, mars_norm, pucs_norm, moes_norm = calibrate()

print ('Starting main application')
time.sleep(1)
infer(ears_norm, mars_norm, pucs_norm, moes_norm)

face_mesh.close()
