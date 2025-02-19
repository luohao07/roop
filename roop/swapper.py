
import os
from tqdm import tqdm
import cv2
import insightface
import threading
import roop.globals
from roop.analyser import get_face_single, get_face_many
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

FACE_SWAPPER = None
THREAD_LOCK = threading.Lock()


def get_face_swapper():
    global FACE_SWAPPER
    with THREAD_LOCK:
        if FACE_SWAPPER is None:
            model_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../inswapper_128.onnx')
            FACE_SWAPPER = insightface.model_zoo.get_model(model_path, providers=roop.globals.providers)
    return FACE_SWAPPER


def swap_face_in_frame(source_face, target_face, frame):
    if target_face:
        return get_face_swapper().get(frame, target_face, source_face, paste_back=True)
    return frame

def process_faces(source_face_1, source_face_2, target_frame):
    if roop.globals.all_faces:
        many_faces = get_face_many(target_frame)
        many_faces = sorted(many_faces, key=lambda x: x['bbox'][0])
        many_faces = [face for face in many_faces if face['gender'] == 0]
        if (not many_faces) :
            return
        if len(many_faces) >= 1:
            target_frame = swap_face_in_frame(source_face_1, many_faces[0], target_frame)
        if len(many_faces) >= 2:
            target_frame = swap_face_in_frame(source_face_2, many_faces[1], target_frame)
    else:
        face = get_face_single(target_frame)
        if face:
            target_frame = swap_face_in_frame(source_face_1, face, target_frame)
    return target_frame

def sort_by_target_faces(many_faces, target_faces):
    # 检查特殊情况
    if target_faces is None or len(target_faces) == 0:
        return many_faces
    elif len(target_faces) > len(many_faces):
        target_faces = target_faces[:len(many_faces)]

    # 计算相似度并排序
    similarities = []
    for i in range(len(target_faces)):
        face = many_faces[i]
        target_face = target_faces[i]
        similarity = calculate_similarity(face.embedding, target_face.embedding)  # 使用你的相似度计算方法
        similarities.append(similarity)

    sorted_faces = [x for _, x in sorted(zip(similarities, many_faces), reverse=True)]
    return sorted_faces

def calculate_similarity(embedding1, embedding2):
    embedding1 = np.array(embedding1).reshape(1, -1)  # 转换为二维数组
    embedding2 = np.array(embedding2).reshape(1, -1)  # 转换为二维数组

    return cosine_similarity(embedding1, embedding2)[0, 0]

def process_frames(args, frame_paths, progress=None):
    source_face1 = get_face_single(cv2.imread(args.source_img1))
    source_face2 = get_face_single(cv2.imread(args.source_img2))
    for frame_path in frame_paths:
        frame = cv2.imread(frame_path)
        try:
            result = process_faces(source_face1, source_face2, frame)
            cv2.imwrite(frame_path, result)
        except Exception as exception:
            print(exception)
            pass
        if progress:
            progress.update(1)


def multi_process_frame(args, frame_paths, progress):
    threads = []
    num_threads = roop.globals.gpu_threads
    num_frames_per_thread = len(frame_paths) // num_threads
    remaining_frames = len(frame_paths) % num_threads

    # create thread and launch
    start_index = 0
    for _ in range(num_threads):
        end_index = start_index + num_frames_per_thread
        if remaining_frames > 0:
            end_index += 1
            remaining_frames -= 1
        thread_frame_paths = frame_paths[start_index:end_index]
        thread = threading.Thread(target=process_frames, args=(args, thread_frame_paths, progress))
        threads.append(thread)
        thread.start()
        start_index = end_index

    # threading
    for thread in threads:
        thread.join()


def process_img(source_img, target_path, output_file):
    frame = cv2.imread(target_path)
    face = get_face_single(frame)
    source_face = get_face_single(cv2.imread(source_img))
    result = get_face_swapper().get(frame, face, source_face, paste_back=True)
    cv2.imwrite(output_file, result)
    print("\n\nImage saved as:", output_file, "\n\n")


def process_video(args, frame_paths):
    do_multi = roop.globals.gpu_vendor is not None and roop.globals.gpu_threads > 1
    progress_bar_format = '{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
    with tqdm(total=len(frame_paths), desc="Processing", unit="frame", dynamic_ncols=True, bar_format=progress_bar_format) as progress:
        if do_multi:
            multi_process_frame(args, frame_paths, progress)
        else:
            process_frames(args, frame_paths, progress)
