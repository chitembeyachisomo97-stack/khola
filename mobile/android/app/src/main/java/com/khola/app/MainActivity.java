package com.khola.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.widget.Toast;
import android.view.View;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.chaquo.python.PyObject;

import java.io.File;
import java.io.InputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {

    private WebView webView;
    private TextView status;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);

        status = new TextView(this);
        status.setText("Starting KHOLA...");
        status.setTextSize(20);
        status.setGravity(Gravity.CENTER);
        layout.addView(status);

        setContentView(layout);

        executor.execute(() -> {
            try {
                File resourceDir = new File(getFilesDir(), "khola_resources");
                File dataDir = new File(getFilesDir(), "khola_data");

                copyAssetFolder("khola", resourceDir);
                if (!dataDir.exists()) dataDir.mkdirs();

                if (!Python.isStarted()) {
                    Python.start(new AndroidPlatform(this));
                }

                Python python = Python.getInstance();
                PyObject launcher = python.getModule("android_app");

                PyObject result = launcher.callAttr(
                    "start_server",
                    dataDir.getAbsolutePath(),
                    resourceDir.getAbsolutePath()
                );

                String serverUrl = result.toString();

                runOnUiThread(() -> openKHOLA(serverUrl));

            } catch (Exception e) {
                runOnUiThread(() -> {
                    status.setText("KHOLA could not start:\n" + e.getMessage());
                });
            }
        });
    }

    private void openKHOLA(String url) {
        webView = new WebView(this);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());

        setContentView(webView);
        webView.loadUrl(url);
    }

    private void copyAssetFolder(String assetPath, File destination)
            throws IOException {

        String[] files = getAssets().list(assetPath);

        if (files == null || files.length == 0) {
            File parent = destination.getParentFile();
            if (parent != null) parent.mkdirs();

            try (InputStream input = getAssets().open(assetPath);
                 FileOutputStream output = new FileOutputStream(destination)) {

                byte[] buffer = new byte[8192];
                int length;

                while ((length = input.read(buffer)) > 0) {
                    output.write(buffer, 0, length);
                }
            }
            return;
        }

        if (!destination.exists()) destination.mkdirs();

        for (String file : files) {
            copyAssetFolder(
                assetPath + "/" + file,
                new File(destination, file)
            );
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        executor.shutdown();
        super.onDestroy();
    }
}
