import onnxruntime

all_faces = None
log_level = 'error'
cpu_cores = None
gpu_threads = None
gpu_vendor = None
providers = onnxruntime.get_available_providers()
target_faces = None

if 'TensorrtExecutionProvider' in providers:
    providers.remove('TensorrtExecutionProvider')
