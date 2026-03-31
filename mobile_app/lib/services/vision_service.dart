import 'dart:async';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import '../utils/constants.dart';

class VisionService {
  CameraController? _cameraController;
  Timer? _frameTimer;
  bool _isActive = false;
  Duration _frameInterval = Duration(seconds: Constants.visionFrameIntervalSeconds);
  final void Function(Uint8List frame)? onFrameCaptured;

  VisionService({this.onFrameCaptured});

  bool get isActive => _isActive;

  Future<CameraController?> initCamera({bool front = true}) async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) return null;

    final target = cameras.firstWhere(
      (c) => c.lensDirection ==
          (front ? CameraLensDirection.front : CameraLensDirection.back),
      orElse: () => cameras.first,
    );

    _cameraController = CameraController(
      target,
      ResolutionPreset.medium,
      enableAudio: false,
    );
    await _cameraController!.initialize();
    return _cameraController;
  }

  CameraController? get cameraController => _cameraController;

  void startContinuousVision() {
    if (_isActive || _cameraController == null) return;
    _isActive = true;
    _frameTimer = Timer.periodic(_frameInterval, (_) => _captureFrame());
  }

  void stopContinuousVision() {
    _isActive = false;
    _frameTimer?.cancel();
    _frameTimer = null;
  }

  void setFrameInterval(Duration interval) {
    _frameInterval = interval;
    if (_isActive) {
      stopContinuousVision();
      startContinuousVision();
    }
  }

  Future<void> _captureFrame() async {
    if (!_isActive || _cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }
    try {
      final xFile = await _cameraController!.takePicture();
      final bytes = await xFile.readAsBytes();
      onFrameCaptured?.call(bytes);
    } catch (e) {
      debugPrint('Vision frame capture error: $e');
    }
  }

  Future<Uint8List?> captureOnce() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) return null;
    try {
      final xFile = await _cameraController!.takePicture();
      return await xFile.readAsBytes();
    } catch (e) {
      debugPrint('Vision capture error: $e');
      return null;
    }
  }

  Future<void> dispose() async {
    stopContinuousVision();
    await _cameraController?.dispose();
    _cameraController = null;
  }
}
