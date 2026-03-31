import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';

class VrmService {
  static const _prefKey = 'selected_vrm_path';

  Future<String?> pickAndSaveVrm() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.any,
      allowMultiple: false,
    );
    if (result == null || result.files.isEmpty) return null;

    final file = result.files.first;
    if (file.path == null) return null;

    if (!file.name.endsWith('.vrm')) {
      throw FormatException('File must be a .vrm file');
    }

    if (file.size > Constants.maxVrmFileSizeBytes) {
      throw FormatException('File exceeds ${Constants.maxVrmFileSizeMB}MB limit');
    }

    // Validate glTF magic bytes
    final bytes = await File(file.path!).openRead(0, 4).first;
    if (bytes.length < 4 ||
        bytes[0] != 0x67 || bytes[1] != 0x6C ||
        bytes[2] != 0x54 || bytes[3] != 0x46) {
      throw FormatException('Invalid VRM file: not a valid glTF file');
    }

    final appDir = await getApplicationDocumentsDirectory();
    final vrmDir = Directory('${appDir.path}/vrm_models');
    if (!vrmDir.existsSync()) {
      vrmDir.createSync(recursive: true);
    }
    final destPath = '${vrmDir.path}/${file.name}';
    await File(file.path!).copy(destPath);

    await setSelectedVrm(destPath);
    return destPath;
  }

  Future<String> getSelectedVrm() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefKey) ?? Constants.defaultVrmModel;
  }

  Future<void> setSelectedVrm(String path) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefKey, path);
  }

  Future<List<String>> listLocalVrm() async {
    final appDir = await getApplicationDocumentsDirectory();
    final vrmDir = Directory('${appDir.path}/vrm_models');
    if (!vrmDir.existsSync()) return [];
    return vrmDir
        .listSync()
        .whereType<File>()
        .where((f) => f.path.endsWith('.vrm'))
        .map((f) => f.path)
        .toList();
  }

  Future<void> deleteLocalVrm(String path) async {
    final file = File(path);
    if (await file.exists()) {
      await file.delete();
    }
    final selected = await getSelectedVrm();
    if (selected == path) {
      await setSelectedVrm(Constants.defaultVrmModel);
    }
  }
}
