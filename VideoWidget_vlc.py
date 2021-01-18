'''
DD监控室最重要的模块之一 视频播放窗口 现已全部从QMediaPlayer迁移至VLC内核播放（klite问题是在太多了。。。）
包含视频缓存播放、音量管理、弹幕窗
遇到不确定的播放状态就调用MediaReload()函数 我已经在里面写好了全部的处理 会自动获取直播间状态并进行对应的刷新操作
'''
import requests, json, os, time
from PyQt5.Qt import *
from remote import remoteThread
import vlc


header = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
}


class Bar(QLabel):
    moveSignal = pyqtSignal(QPoint)

    def __init__(self, text):
        super(Bar, self).__init__()
        self.setText(text)
        self.setFixedHeight(25)

    def mousePressEvent(self, event):
        self.startPos = event.pos()

    def mouseMoveEvent(self, event):
        self.moveSignal.emit(event.pos() - self.startPos)


class ToolButton(QToolButton):
    def __init__(self, icon):
        super(ToolButton, self).__init__()
        self.setStyleSheet('border-color:#CCCCCC')
        self.setFixedSize(25, 25)
        self.setIcon(icon)


class TextOpation(QWidget):
    def __init__(self, setting=[20, 2, 6, 0, '【 [ {']):
        super(TextOpation, self).__init__()
        self.resize(300, 300)
        self.setWindowTitle('弹幕窗设置')
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        layout = QGridLayout(self)
        layout.addWidget(QLabel('窗体颜色浓度'), 0, 0, 1, 1)
        self.opacitySlider = Slider()
        self.opacitySlider.setValue(setting[0])
        layout.addWidget(self.opacitySlider, 0, 1, 1, 1)
        layout.addWidget(QLabel('窗体横向占比'), 1, 0, 1, 1)
        self.horizontalCombobox = QComboBox()
        self.horizontalCombobox.addItems(['10%', '15%', '20%', '25%', '30%', '35%', '40%', '45%', '50%'])
        self.horizontalCombobox.setCurrentIndex(setting[1])
        layout.addWidget(self.horizontalCombobox, 1, 1, 1, 1)
        layout.addWidget(QLabel('窗体纵向占比'), 2, 0, 1, 1)
        self.verticalCombobox = QComboBox()
        self.verticalCombobox.addItems(['50%', '55%', '60%', '65%', '70%', '75%', '80%', '85%', '90%', '95%', '100%'])
        self.verticalCombobox.setCurrentIndex(setting[2])
        layout.addWidget(self.verticalCombobox, 2, 1, 1, 1)
        layout.addWidget(QLabel('单独同传窗口'), 3, 0, 1, 1)
        self.translateCombobox = QComboBox()
        self.translateCombobox.addItems(['开启', '关闭'])
        self.translateCombobox.setCurrentIndex(setting[3])
        layout.addWidget(self.translateCombobox, 3, 1, 1, 1)
        layout.addWidget(QLabel('同传过滤字符 (空格隔开)'), 4, 0, 1, 1)
        self.translateFitler = QLineEdit('')
        self.translateFitler.setText(setting[4])
        self.translateFitler.setFixedWidth(100)
        layout.addWidget(self.translateFitler, 4, 1, 1, 1)


class TextBrowser(QWidget):
    closeSignal = pyqtSignal()

    def __init__(self, parent):
        super(TextBrowser, self).__init__(parent)
        self.optionWidget = TextOpation()
        # self.resize(60, 200)

        # self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.bar = Bar(' 弹幕机')
        self.bar.setStyleSheet('background:#AAAAAAAA')
        self.bar.moveSignal.connect(self.moveWindow)
        layout.addWidget(self.bar, 0, 0, 1, 10)

        self.optionButton = ToolButton(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.optionButton.clicked.connect(self.optionWidget.show)  # 弹出设置菜单
        layout.addWidget(self.optionButton, 0, 8, 1, 1)

        self.closeButton = ToolButton(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.closeButton.clicked.connect(self.userClose)
        layout.addWidget(self.closeButton, 0, 9, 1, 1)

        self.textBrowser = QTextBrowser()
        self.textBrowser.setFont(QFont('Microsoft JhengHei', 16, QFont.Bold))
        self.textBrowser.setStyleSheet('border-width:1')
        layout.addWidget(self.textBrowser, 1, 0, 1, 10)

        self.transBrowser = QTextBrowser()
        self.transBrowser.setFont(QFont('Microsoft JhengHei', 16, QFont.Bold))
        self.transBrowser.setStyleSheet('border-width:1')
        # self.transBrowser.setFixedHeight(self.height() / 3)
        layout.addWidget(self.transBrowser, 2, 0, 1, 10)

    def userClose(self):
        self.hide()
        self.closeSignal.emit()

    def moveWindow(self, moveDelta):
        newPos = self.pos() + moveDelta
        x, y = newPos.x(), newPos.y()
        rightBorder = self.parent().width() - self.width()
        bottomBoder = self.parent().height() - self.height()
        if x < 0:
            x = 0
        elif x > rightBorder:
            x = rightBorder
        if y < 30:
            y = 30
        elif y > bottomBoder:
            y = bottomBoder
        self.move(x, y)


class PushButton(QPushButton):
    def __init__(self, icon='', text=''):
        super(PushButton, self).__init__()
        self.setFixedSize(30, 30)
        self.setStyleSheet('background-color:#00000000')
        if icon:
            self.setIcon(icon)
        elif text:
            self.setText(text)


class Slider(QSlider):
    value = pyqtSignal(int)

    def __init__(self, value=100):
        super(Slider, self).__init__()
        self.setOrientation(Qt.Horizontal)
        self.setFixedWidth(100)
        self.setValue(value)

    def mousePressEvent(self, event):
        self.updateValue(event.pos())

    def mouseMoveEvent(self, event):
        self.updateValue(event.pos())

    def wheelEvent(self, event):  # 把进度条的滚轮事件去了 用啥子滚轮
        pass

    def updateValue(self, QPoint):
        value = QPoint.x()
        if value > 100: value = 100
        elif value < 0: value = 0
        self.setValue(value)
        self.value.emit(value)


class GetMediaURL(QThread):
    cacheName = pyqtSignal(str)
    downloadError = pyqtSignal()

    def __init__(self, id, cacheFolder):
        super(GetMediaURL, self).__init__()
        self.id = id
        self.cacheFolder = cacheFolder
        self.roomID = '0'
        self.recordToken = False
        self.quality = 250
        self.downloadToken = False
        self.checkTimer = QTimer()
        self.checkTimer.timeout.connect(self.checkDownlods)

    def checkDownlods(self):
        if self.downloadToken:
            self.downloadToken = False
        else:
            self.downloadError.emit()

    def setConfig(self, roomID, quality):
        self.roomID = roomID
        self.quality = quality

    def run(self):
        maxCount = {10000: 1500, 400: 1000, 250: 800, 80: 500}[self.quality]
        api = r'https://api.live.bilibili.com/room/v1/Room/playUrl?cid=%s&platform=web&qn=%s' % (self.roomID, self.quality)
        r = requests.get(api)
        try:
            url = json.loads(r.text)['data']['durl'][0]['url']
            fileName = '%s/%s.flv' % (self.cacheFolder, self.id)
            download = requests.get(url, stream=True, headers=header)
            self.recordToken = True
            contentCnt = 0
            while True:
                try:
                    self.cacheVideo = open(fileName, 'wb')  # 等待上次缓存关闭
                    break
                except:
                    time.sleep(0.05)
            for chunk in download.iter_content(chunk_size=512):
                if not self.recordToken:
                    break
                if chunk:
                    self.downloadToken = True
                    self.cacheVideo.write(chunk)
                    contentCnt += 1
                    if not contentCnt % 2048000:  # 缓存超过1GB清除缓存刷新一次 原画大约要20分钟-30分钟
                        self.downloadError.emit()
                    elif contentCnt == maxCount:
                        self.cacheName.emit(fileName)
            self.cacheVideo.close()
            os.remove(fileName)  # 清除缓存
        except Exception as e:
            print(str(e))


class VideoFrame(QFrame):
    rightClicked = pyqtSignal(QEvent)
    leftClicked = pyqtSignal()
    doubleClicked = pyqtSignal()

    def __init__(self):
        super(VideoFrame, self).__init__()
        self.setAcceptDrops(True)

    def mousePressEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.RightButton:
            self.rightClicked.emit(QMouseEvent)
        elif QMouseEvent.button() == Qt.LeftButton:
            self.leftClicked.emit()

    def mouseDoubleClickEvent(self, QMouseEvent):
        self.doubleClicked.emit()

    # def dropEvent(self, QEvent):
    #     if QEvent.mimeData().hasText:
    #         print(QEvent.mimeData().text())


class VideoWidget(QWidget):
    mutedChanged = pyqtSignal(list)
    volumeChanged = pyqtSignal(list)
    addMedia = pyqtSignal(list)  # 发送新增的直播
    deleteMedia = pyqtSignal(int)  # 删除选中的直播
    exchangeMedia = pyqtSignal(list)  # 交换播放窗口
    setDanmu = pyqtSignal(list)  # 发射弹幕关闭信号
    setTranslator = pyqtSignal(list)  # 发送同传关闭信号
    changeQuality = pyqtSignal(list)  # 修改画质
    popWindow = pyqtSignal(list)  # 弹出悬浮窗
    hideBarKey = pyqtSignal()  # 隐藏控制条快捷键
    fullScreenKey = pyqtSignal()  # 全屏快捷键
    muteExceptKey = pyqtSignal()  # 除了这个播放器 其他全部静音快捷键

    def __init__(self, id, volume, cacheFolder, top=False, title='', resize=[], textSetting=[True, 20, 2, 6, 0, '【 [ {']):
        super(VideoWidget, self).__init__()
        self.setAcceptDrops(True)
        self.installEventFilter(self)
        self.id = id
        self.hoverToken = False
        self.roomID = '0'  # 初始化直播间房号
        self.liveStatus = 0  # 初始化直播状态为0
        self.pauseToken = False
        self.quality = 250
        self.volume = volume
        self.leftButtonPress = False
        self.rightButtonPress = False
        self.fullScreen = False
        self.top = top
        if top:  # 悬浮窗取消关闭按钮 vlc版点关闭后有bug 让用户右键退出
            self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.textSetting = textSetting
        self.horiPercent = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5][self.textSetting[2]]
        self.vertPercent = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1][self.textSetting[3]]
        self.filters = textSetting[5].split(' ')
        self.opacity = 100
        if top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint)
        if title:
            if top:
                self.setWindowTitle('%s %s' % (title, id + 1 - 9))
            else:
                self.setWindowTitle('%s %s' % (title, id + 1))
        if resize:
            self.resize(resize[0], resize[1])
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        videoFrame = VideoFrame()  # 新版本vlc内核播放器
        videoFrame.rightClicked.connect(self.rightMouseClicked)
        videoFrame.leftClicked.connect(self.leftMouseClicked)
        videoFrame.doubleClicked.connect(self.doubleClick)
        layout.addWidget(videoFrame, 0, 0, 12, 12)
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()  # 视频播放
        self.player.video_set_mouse_input(False)
        self.player.video_set_key_input(False)
        self.player.set_hwnd(videoFrame.winId())

        self.topLabel = QLabel()
        self.topLabel.setFixedHeight(30)
        # self.topLabel.setAlignment(Qt.AlignCenter)
        self.topLabel.setObjectName('frame')
        self.topLabel.setStyleSheet("background-color:#BB708090")
        # self.topLabel.setFixedHeight(32)
        self.topLabel.setFont(QFont('微软雅黑', 15, QFont.Bold))
        layout.addWidget(self.topLabel, 0, 0, 1, 12)
        self.topLabel.hide()

        self.frame = QWidget()
        self.frame.setObjectName('frame')
        self.frame.setStyleSheet("background-color:#BB708090")
        self.frame.setFixedHeight(50)
        frameLayout = QHBoxLayout(self.frame)
        frameLayout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.frame, 11, 0, 1, 12)
        self.frame.hide()

        self.titleLabel = QLabel()
        self.titleLabel.setMaximumWidth(150)
        self.titleLabel.setStyleSheet('background-color:#00000000')
        self.setTitle()
        frameLayout.addWidget(self.titleLabel)
        self.play = PushButton(self.style().standardIcon(QStyle.SP_MediaPause))
        self.play.clicked.connect(self.mediaPlay)
        frameLayout.addWidget(self.play)
        self.reload = PushButton(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.reload.clicked.connect(self.mediaReload)
        frameLayout.addWidget(self.reload)
        self.volumeButton = PushButton(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.volumeButton.clicked.connect(self.mediaMute)
        frameLayout.addWidget(self.volumeButton)
        self.slider = Slider()
        self.slider.setStyleSheet('background-color:#00000000')
        self.slider.value.connect(self.setVolume)
        frameLayout.addWidget(self.slider)
        self.danmuButton = PushButton(text='弹')
        self.danmuButton.clicked.connect(self.showDanmu)
        frameLayout.addWidget(self.danmuButton)
        self.stop = PushButton(self.style().standardIcon(QStyle.SP_DialogCancelButton))
        self.stop.clicked.connect(self.mediaStop)
        frameLayout.addWidget(self.stop)

        self.getMediaURL = GetMediaURL(self.id, cacheFolder)
        self.getMediaURL.cacheName.connect(self.setMedia)
        self.getMediaURL.downloadError.connect(self.mediaReload)

        self.textBrowser = TextBrowser(self)
        self.setDanmuOpacity(self.textSetting[1])  # 设置弹幕透明度
        self.textBrowser.optionWidget.opacitySlider.setValue(self.textSetting[1])  # 设置选项页透明条
        self.textBrowser.optionWidget.opacitySlider.value.connect(self.setDanmuOpacity)
        self.setHorizontalPercent(self.textSetting[2])  # 设置横向占比
        self.textBrowser.optionWidget.horizontalCombobox.setCurrentIndex(self.textSetting[2])  # 设置选项页占比框
        self.textBrowser.optionWidget.horizontalCombobox.currentIndexChanged.connect(self.setHorizontalPercent)
        self.setVerticalPercent(self.textSetting[3])  # 设置横向占比
        self.textBrowser.optionWidget.verticalCombobox.setCurrentIndex(self.textSetting[3])  # 设置选项页占比框
        self.textBrowser.optionWidget.verticalCombobox.currentIndexChanged.connect(self.setVerticalPercent)
        self.setTranslateBrowser(self.textSetting[4])
        self.textBrowser.optionWidget.translateCombobox.setCurrentIndex(self.textSetting[4])  # 设置同传窗口
        self.textBrowser.optionWidget.translateCombobox.currentIndexChanged.connect(self.setTranslateBrowser)
        self.setTranslateFilter(self.textSetting[5])  # 同传过滤字符
        self.textBrowser.optionWidget.translateFitler.setText(self.textSetting[5])
        self.textBrowser.optionWidget.translateFitler.textChanged.connect(self.setTranslateFilter)
        self.textBrowser.closeSignal.connect(self.closeDanmu)

        # self.translator = TextBrowser(self, self.id, '同传')
        # self.translator.closeSignal.connect(self.closeTranslator)

        self.danmu = remoteThread(self.roomID)

        # self.moveTimer = QTimer()
        # self.moveTimer.timeout.connect(self.moveTextBrowser)
        # self.moveTimer.start(50)

    def setDanmuOpacity(self, value):
        if value < 7: value = 7  # 最小透明度
        self.textSetting[1] = value  # 记录设置
        value = int(value / 101 * 256)
        color = str(hex(value))[2:] + '000000'
        self.textBrowser.textBrowser.setStyleSheet('background-color:#%s' % color)
        self.textBrowser.transBrowser.setStyleSheet('background-color:#%s' % color)

    def setHorizontalPercent(self, index):  # 设置弹幕框水平宽度
        self.textSetting[2] = index
        self.horiPercent = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5][index]  # 记录横向占比
        width = self.width() * self.horiPercent
        self.textBrowser.resize(width, self.textBrowser.height())
        if width > 300:
            self.textBrowser.textBrowser.setFont(QFont('Microsoft JhengHei', 20, QFont.Bold))
            self.textBrowser.transBrowser.setFont(QFont('Microsoft JhengHei', 20, QFont.Bold))
        elif 100 < width <= 300:
            self.textBrowser.textBrowser.setFont(QFont('Microsoft JhengHei', width // 20 + 5, QFont.Bold))
            self.textBrowser.transBrowser.setFont(QFont('Microsoft JhengHei', width // 20 + 5, QFont.Bold))
        else:
            self.textBrowser.textBrowser.setFont(QFont('Microsoft JhengHei', 10, QFont.Bold))
            self.textBrowser.transBrowser.setFont(QFont('Microsoft JhengHei', 10, QFont.Bold))
        self.textBrowser.textBrowser.verticalScrollBar().setValue(100000000)
        self.textBrowser.transBrowser.verticalScrollBar().setValue(100000000)

    def setVerticalPercent(self, index):  # 设置弹幕框垂直高度
        self.textSetting[3] = index
        self.vertPercent = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1][index]  # 记录纵向占比
        self.textBrowser.resize(self.textBrowser.width(), self.height() * self.vertPercent)
        self.textBrowser.textBrowser.verticalScrollBar().setValue(100000000)
        self.textBrowser.transBrowser.verticalScrollBar().setValue(100000000)

    def setTranslateBrowser(self, index):
        self.textSetting[4] = index
        self.textBrowser.transBrowser.show() if not index else self.textBrowser.transBrowser.hide()  # 显示/隐藏同传
        self.textBrowser.adjustSize()
        self.resize(self.width() * self.horiPercent, self.height() * self.vertPercent)

    def setTranslateFilter(self, filterWords):
        self.filters = filterWords.split(' ')

    def enterEvent(self, QEvent):
        self.hoverToken = True
        self.topLabel.show()
        self.frame.show()

    def leaveEvent(self, QEvent):
        self.hoverToken = False
        self.topLabel.hide()
        self.frame.hide()

    def doubleClick(self):
        if not self.top:  # 非弹出类悬浮窗
            self.popWindow.emit([self.id, self.roomID, self.quality, True])
            self.mediaPlay(1)  # 暂停播放

    def leftMouseClicked(self):  # 设置drag事件 发送拖动封面的房间号
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setText('exchange:%s:%s' % (self.id, self.roomID))
        drag.setMimeData(mimeData)
        drag.exec_()

    def dragEnterEvent(self, QDragEnterEvent):
        QDragEnterEvent.accept()

    def dropEvent(self, QDropEvent):
        if QDropEvent.mimeData().hasText:
            text = QDropEvent.mimeData().text()  # 拖拽事件
            if 'roomID' in text:  # 从cover拖拽新直播间
                self.roomID = text.split(':')[1]
                self.addMedia.emit([self.id, self.roomID])
                self.mediaReload()
                self.textBrowser.textBrowser.clear()
                self.textBrowser.transBrowser.clear()
            elif 'exchange' in text:  # 交换窗口
                fromID, fromRoomID = text.split(':')[1:]  # exchange:id:roomID
                fromID = int(fromID)
                if fromID != self.id:
                    self.exchangeMedia.emit([fromID, fromRoomID, self.id, self.roomID])
                    # self.roomID = fromRoomID
                    # self.mediaReload()

    def rightMouseClicked(self, event):
        menu = QMenu()
        openBrowser = menu.addAction('打开直播间')
        chooseQuality = menu.addMenu('选择画质')
        originQuality = chooseQuality.addAction('原画')
        if self.quality == 10000:
            originQuality.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        bluerayQuality = chooseQuality.addAction('蓝光')
        if self.quality == 400:
            bluerayQuality.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        highQuality = chooseQuality.addAction('超清')
        if self.quality == 250:
            highQuality.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        lowQuality = chooseQuality.addAction('流畅')
        if self.quality == 80:
            lowQuality.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        if not self.top:  # 非弹出类悬浮窗
            popWindow = menu.addAction('悬浮窗播放')
        else:
            opacityMenu = menu.addMenu('调节透明度')
            percent100 = opacityMenu.addAction('100%')
            if self.opacity == 100:
                percent100.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
            percent80 = opacityMenu.addAction('80%')
            if self.opacity == 80:
                percent80.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
            percent60 = opacityMenu.addAction('60%')
            if self.opacity == 60:
                percent60.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
            percent40 = opacityMenu.addAction('40%')
            if self.opacity == 40:
                percent40.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
            percent20 = opacityMenu.addAction('20%')
            if self.opacity == 20:
                percent20.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
            fullScreen = menu.addAction('退出全屏') if self.isFullScreen() else menu.addAction('全屏')
            exit = menu.addAction('退出')
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == openBrowser:
            if self.roomID != '0':
                QDesktopServices.openUrl(QUrl(r'https://live.bilibili.com/%s' % self.roomID))
        elif action == originQuality:
            self.changeQuality.emit([self.id, 10000])
            self.quality = 10000
            self.mediaReload()
        elif action == bluerayQuality:
            self.changeQuality.emit([self.id, 400])
            self.quality = 400
            self.mediaReload()
        elif action == highQuality:
            self.changeQuality.emit([self.id, 250])
            self.quality = 250
            self.mediaReload()
        elif action == lowQuality:
            self.changeQuality.emit([self.id, 80])
            self.quality = 80
            self.mediaReload()
        if not self.top:
            if action == popWindow:
                self.popWindow.emit([self.id, self.roomID, self.quality, False])
                self.mediaPlay(1)  # 暂停播放
        elif self.top:
            if action == percent100:
                self.setWindowOpacity(1)
                self.opacity = 100
            elif action == percent80:
                self.setWindowOpacity(0.8)
                self.opacity = 80
            elif action == percent60:
                self.setWindowOpacity(0.6)
                self.opacity = 60
            elif action == percent40:
                self.setWindowOpacity(0.4)
                self.opacity = 40
            elif action == percent20:
                self.setWindowOpacity(0.2)
                self.opacity = 20
            elif action == fullScreen:
                if self.isFullScreen():
                    self.showNormal()
                else:
                    self.showFullScreen()
            elif action == exit:
                self.hide()
                self.mediaStop()

    def resizeEvent(self, QEvent):
        # self.scene.setSceneRect(1, 1, self.width() - 2, self.height() - 2)
        width = self.width() * self.horiPercent
        self.textBrowser.resize(width, self.height() * self.vertPercent)
        if width > 300:
            self.textBrowser.textBrowser.setFont(QFont('Microsoft JhengHei', 20, QFont.Bold))
            self.textBrowser.transBrowser.setFont(QFont('Microsoft JhengHei', 20, QFont.Bold))
        elif 100 < width <= 300:
            self.textBrowser.textBrowser.setFont(QFont('Microsoft JhengHei', width // 20 + 5, QFont.Bold))
            self.textBrowser.transBrowser.setFont(QFont('Microsoft JhengHei', width // 20 + 5, QFont.Bold))
        else:
            self.textBrowser.textBrowser.setFont(QFont('Microsoft JhengHei', 10, QFont.Bold))
            self.textBrowser.transBrowser.setFont(QFont('Microsoft JhengHei', 10, QFont.Bold))
        # if not self.textBrowser.transBrowser.isHidden():
        #     self.textBrowser.transBrowser.setFixedHeight(self.textBrowser.height() / 3)

        self.textBrowser.move(0, 30)
        self.textBrowser.textBrowser.verticalScrollBar().setValue(100000000)
        self.textBrowser.transBrowser.verticalScrollBar().setValue(100000000)
        # self.resizeTimer.start(50)  # 延迟50ms修改video窗口 否则容易崩溃

    # def resizeVideoItem(self):
    #     self.resizeTimer.stop()
    #     self.videoItem.setSize(QSizeF(self.width(), self.height()))

    def setVolume(self, value):
        self.player.audio_set_volume(value)
        self.volume = value  # 记录volume值 每次刷新要用到
        self.slider.setValue(value)
        self.volumeChanged.emit([self.id, value])

    def closeDanmu(self):
        self.textSetting[0] = False
        # self.setDanmu.emit([self.id, False])  # 旧版信号 已弃用

    def closeTranslator(self):
        self.setTranslator.emit([self.id, False])

    def showDanmu(self):
        if self.textBrowser.isHidden():
            self.textBrowser.show()
            # self.translator.show()
        else:
            self.textBrowser.hide()
            # self.translator.hide()
        self.textSetting[0] = not self.textBrowser.isHidden()
        # self.setDanmu.emit([self.id, not self.textBrowser.isHidden()])
        # self.setTranslator.emit([self.id, not self.translator.isHidden()])

    def mediaPlay(self, force=0):
        if force == 1:
            self.player.set_pause(1)
            self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        elif force == 2:
            self.player.play()
            self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        elif self.player.get_state() == vlc.State.Playing:
            self.player.pause()
            self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            self.player.play()
            self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def mediaMute(self, force=0, emit=True):
        if force == 1:
            self.player.audio_set_mute(False)
            self.volumeButton.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        elif force == 2:
            self.player.audio_set_mute(True)
            self.volumeButton.setIcon(self.style().standardIcon(QStyle.SP_MediaVolumeMuted))
        elif self.player.audio_get_mute():
            self.player.audio_set_mute(False)
            self.volumeButton.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        else:
            self.player.audio_set_mute(True)
            self.volumeButton.setIcon(self.style().standardIcon(QStyle.SP_MediaVolumeMuted))
        if emit:
            self.mutedChanged.emit([self.id, self.player.audio_get_mute()])

    def mediaReload(self):
        self.getMediaURL.recordToken = False  # 设置停止缓存标志位
        self.getMediaURL.checkTimer.stop()
        self.player.stop()
        if self.roomID != '0':
            self.setTitle()  # 同时获取最新直播状态
            if self.liveStatus == 1:  # 直播中
                self.getMediaURL.setConfig(self.roomID, self.quality)  # 设置房号和画质
                self.getMediaURL.start()  # 开始缓存视频
                self.getMediaURL.checkTimer.start(3000)  # 启动监测定时器
        else:
            self.mediaStop()

    def mediaStop(self):
        self.roomID = '0'
        self.topLabel.setText('    窗口%s  未定义的直播间' % (self.id + 1))
        self.titleLabel.setText('未定义')
        self.player.stop()
        self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.deleteMedia.emit(self.id)
        try:
            self.danmu.message.disconnect(self.playDanmu)
        except:
            pass
        self.getMediaURL.recordToken = False
        self.getMediaURL.checkTimer.stop()
        self.danmu.terminate()
        self.danmu.quit()
        self.danmu.wait()

    def setMedia(self, cacheName):
        self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.danmu.setRoomID(self.roomID)
        try:
            self.danmu.message.disconnect(self.playDanmu)
        except:
            pass
        self.danmu.message.connect(self.playDanmu)
        self.danmu.terminate()
        self.danmu.start()
        self.media = self.instance.media_new(cacheName, 'avcodec-hw=dxva2')  # 设置vlc并硬解播放
        self.player.set_media(self.media)  # 设置视频
        self.player.play()

    def setTitle(self):
        if self.roomID == '0':
            title = '未定义的直播间'
            uname = '未定义'
        else:
            r = requests.get(r'https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id=%s' % self.roomID)
            data = json.loads(r.text)
            if data['message'] == '房间已加密':
                title = '房间已加密'
                uname = '房号: %s' % self.roomID
            elif not data['data']:
                title = '房间好像不见了-_-？'
                uname = '未定义'
            else:
                data = data['data']
                self.liveStatus = data['room_info']['live_status']
                title = data['room_info']['title']
                uname = data['anchor_info']['base_info']['uname']
                if self.liveStatus != 1:
                    uname = '（未开播）' + uname
        self.topLabel.setText('    窗口%s  %s' % (self.id + 1, title))
        self.titleLabel.setText(uname)

    def playDanmu(self, message):
        if self.textBrowser.transBrowser.isHidden():
            self.textBrowser.textBrowser.append(message)
        else:
            token = False
            for symbol in self.filters:
                if symbol in message:
                    self.textBrowser.transBrowser.append(message)
                    token = True
                    break
            if not token:
                self.textBrowser.textBrowser.append(message)

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == Qt.Key_Escape:
            if self.top and self.isFullScreen():  # 悬浮窗退出全屏
                self.showNormal()
            else:
                self.fullScreenKey.emit()  # 主界面退出全屏
        elif QKeyEvent.key() == Qt.Key_H:
            self.hideBarKey.emit()
        elif QKeyEvent.key() == Qt.Key_F:
            self.fullScreenKey.emit()
        elif QKeyEvent.key() == Qt.Key_M:
            self.muteExceptKey.emit()  # 这里调用self.id为啥是0???
