package com.musicdown.netease;

import static com.musicdown.netease.Models.AppException;
import static com.musicdown.netease.Models.AudioInfo;

import android.media.MediaMetadataRetriever;
import android.media.MediaExtractor;
import android.media.MediaFormat;

import java.io.File;
import java.io.FileInputStream;
import java.util.Locale;

final class AudioInspector {
    private AudioInspector() {}

    static AudioInfo inspect(File file) throws AppException {
        byte[] head = new byte[16];
        try (FileInputStream input = new FileInputStream(file)) {
            if (input.read(head) < 4) throw new AppException("下载内容不是有效音频文件");
        } catch (AppException e) {
            throw e;
        } catch (Exception e) {
            throw new AppException("读取音频文件失败：" + e.getMessage(), e);
        }

        String extension;
        String codec;
        boolean lossless;
        if (head[0] == 'f' && head[1] == 'L' && head[2] == 'a' && head[3] == 'C') {
            extension = "flac"; codec = "FLAC"; lossless = true;
        } else if (head.length >= 8 && head[4] == 'f' && head[5] == 't' && head[6] == 'y' && head[7] == 'p') {
            extension = "m4a"; codec = "AAC/ALAC"; lossless = false;
        } else if ((head[0] == 'I' && head[1] == 'D' && head[2] == '3') ||
                ((head[0] & 0xff) == 0xff && ((head[1] & 0xe0) == 0xe0))) {
            extension = "mp3"; codec = "MP3"; lossless = false;
        } else {
            throw new AppException("服务器返回的内容不是支持的 MP3、M4A 或 FLAC 音频");
        }

        MediaMetadataRetriever retriever = new MediaMetadataRetriever();
        try {
            retriever.setDataSource(file.getAbsolutePath());
            double duration = parseLong(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)) / 1000.0;
            int bitrate = (int) (parseLong(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_BITRATE)) / 1000);
            TrackMetadata track = trackMetadata(file);
            String mime = track.mime;
            if (mime == null || mime.isEmpty()) throw new AppException("Android 无法识别该音频实际编码，不能标记为验证成功");
            String normalizedMime = mime.toLowerCase(Locale.ROOT);
            if ("flac".equals(extension) && !normalizedMime.contains("flac"))
                throw new AppException("文件扩展名为 FLAC，但实际音轨编码不匹配");
            if ("mp3".equals(extension) && !(normalizedMime.contains("mpeg") || normalizedMime.contains("mp3")))
                throw new AppException("文件扩展名为 MP3，但实际音轨编码不匹配");
            if ("m4a".equals(extension) && !(normalizedMime.contains("mp4a") || normalizedMime.contains("aac") || normalizedMime.contains("alac")))
                throw new AppException("Android 无法验证此 M4A 特殊编码，未标记为成功（" + mime + "）");
            if (bitrate <= 0 && track.bitrate > 0) bitrate = track.bitrate / 1000;
            if (duration <= 0) throw new AppException("音频文件没有有效时长，未保存");
            if (bitrate <= 0) bitrate = (int) Math.round(file.length() * 8.0 / duration / 1000.0);
            if ("m4a".equals(extension) && mime != null && mime.toLowerCase(Locale.ROOT).contains("alac")) {
                codec = "ALAC"; lossless = true;
            } else if ("m4a".equals(extension) && mime != null &&
                    (mime.toLowerCase(Locale.ROOT).contains("mp4a") || mime.toLowerCase(Locale.ROOT).contains("aac"))) {
                codec = "AAC";
            } else if ("m4a".equals(extension)) {
                throw new AppException("Android 无法可靠判断 M4A 编码，未标记为成功");
            }
            return new AudioInfo(extension, codec, lossless, bitrate, duration);
        } catch (AppException e) {
            throw e;
        } catch (Exception e) {
            throw new AppException("音频文件无法解码：" + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()), e);
        } finally {
            try { retriever.release(); } catch (Exception ignored) {}
        }
    }

    private static long parseLong(String value) {
        try { return value == null ? 0 : Long.parseLong(value); }
        catch (NumberFormatException ignored) { return 0; }
    }

    private static TrackMetadata trackMetadata(File file) {
        MediaExtractor extractor = new MediaExtractor();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            for (int i = 0; i < extractor.getTrackCount(); i++) {
                MediaFormat format = extractor.getTrackFormat(i);
                String mime = format.getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("audio/")) {
                    int bitrate = format.containsKey(MediaFormat.KEY_BIT_RATE) ? format.getInteger(MediaFormat.KEY_BIT_RATE) : 0;
                    return new TrackMetadata(mime, bitrate);
                }
            }
        } catch (Exception ignored) {
        } finally {
            try { extractor.release(); } catch (Exception ignored) {}
        }
        return new TrackMetadata("", 0);
    }

    private static final class TrackMetadata {
        final String mime;
        final int bitrate;
        TrackMetadata(String mime, int bitrate) { this.mime = mime; this.bitrate = bitrate; }
    }
}
