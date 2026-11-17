import os
import re
import sys

import markdown
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QStackedWidget, QScroller, QScrollerProperties, QSizePolicy
from qfluentwidgets import qconfig, ScrollArea, Pivot, TextBrowser, setCustomStyleSheet, PushButton, FluentIcon
from .common.style_sheet import StyleSheet
from module.localization import tr


# 各标签对应的文档：“在官网查看”按钮打开当前标签的同一份文档（按界面语言）
DOC_OF_TAB = {
    'tutorialLabel': 'Tutorial',
    'workflowLabel': 'Workflow',
    'faqLabel': 'FAQ',
    'backgroundLabel': 'Background',
    'tasksLabel': 'TasksTable',
    'changelogLabel': 'Changelog',
}

_LINK_CSS = """a {
    color: #f18cb9;
    font-weight: bold;
}
"""

_TABLE_CSS = """table {
  border-collapse: collapse;
  width: 100%;
}

th, td {
  border: 1px solid black;
  padding: 1px 30px 1px 30px;
  text-align: left;
  font-size: 15px;
}
"""


def _md_style(*blocks):
    """把若干段 CSS 拼成一个 <style> 块，与原内联样式完全等价。"""
    return "<style>\n" + "\n".join(blocks) + "</style>\n"


class HelpInterface(ScrollArea):
    # 标签页 → 渲染方法。每个标签页的 markdown 只在首次切换到时渲染。
    _DOC_BUILDERS = {
        'tutorialLabel': '_buildTutorialDoc',
        'workflowLabel': '_buildWorkflowDoc',
        'faqLabel': '_buildFaqDoc',
        'backgroundLabel': '_buildBackgroundDoc',
        'tasksLabel': '_buildTasksDoc',
        'changelogLabel': '_buildChangelogDoc',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        # 已渲染的标签页与它们的 HTML，供主题切换/语言切换时复用，避免重复跑 markdown。
        self._docContent = {}
        self._builtDocs = set()
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.helpLabel = QLabel(tr("帮助"), self)
        self.websiteButton = PushButton(FluentIcon.GLOBE, tr("在官网查看"), self)
        self.tutorialLabel = TextBrowser(parent)
        self.workflowLabel = TextBrowser(parent)
        self.faqLabel = TextBrowser(parent)
        self.backgroundLabel = TextBrowser(parent)
        self.tasksLabel = TextBrowser(parent)
        self.changelogLabel = TextBrowser(parent)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()
        for attr in DOC_OF_TAB:
            getattr(self, attr).anchorClicked.connect(self.open_url)
        qconfig.themeChanged.connect(self.__themeChanged)

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setObjectName('helpInterface')
        self.scrollWidget.setObjectName('scrollWidget')
        self.helpLabel.setObjectName('helpLabel')
        StyleSheet.HELP_INTERFACE.apply(self)
        self.websiteButton.adjustSize()
        self.websiteButton.clicked.connect(self.openWebsite)

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initCard(self):
        """只渲染首个标签页；其余页在首次切换到时渲染。

        六个帮助页的 markdown 渲染在启动阶段要花两百多毫秒，而其中五页用户未必会看，
        因此全部改为按需渲染。
        """
        self._ensureDocBuilt('tutorialLabel')

    def _ensureDocBuilt(self, name):
        """按需渲染单个帮助页（幂等）。"""
        if name in self._builtDocs:
            return
        method = self._DOC_BUILDERS.get(name)
        if method is None:
            return
        self._builtDocs.add(name)
        self._docContent[name] = getattr(self, method)()
        self._applyDoc(name)

    def _applyDoc(self, name):
        """把已渲染的 HTML 写入对应标签页，暗色主题下修正表格边框颜色。"""
        html = self._docContent.get(name)
        if html is None:
            return
        label = getattr(self, name)
        if qconfig.theme.name == "DARK":
            label.setText(html.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            label.setText(html)
        label.setOpenExternalLinks(True)

    def _read_doc(self, base_name, skip_lines=1, site_links=False):
        path = self._get_localized_doc_path(base_name)
        try:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
        except FileNotFoundError:
            sys.exit(1)
        if site_links:
            content = self._site_links(content)
        return '\n'.join(content.split('\n')[skip_lines:])

    def _buildTutorialDoc(self):
        content = self._read_doc("Tutorial", skip_lines=1, site_links=True)
        return _md_style(_LINK_CSS, _TABLE_CSS) + markdown.markdown(content, extensions=['tables']).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

    def _buildWorkflowDoc(self):
        content = self._read_doc("Workflow", skip_lines=1)
        return _md_style(_LINK_CSS, _TABLE_CSS) + markdown.markdown(content, extensions=['tables']).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

    def _buildFaqDoc(self):
        content = self._read_doc("FAQ", skip_lines=2)
        return _md_style(_LINK_CSS) + markdown.markdown(content).replace('<h3>', '<br><h3>').replace('</h3>', '</h3><hr>').replace('<br>', '', 1) + '<br>'

    def _buildBackgroundDoc(self):
        content = self._read_doc("Background", skip_lines=1, site_links=True)
        return _md_style(_LINK_CSS, _TABLE_CSS) + markdown.markdown(content, extensions=['tables', 'fenced_code']).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

    def _buildTasksDoc(self):
        content = self._read_doc("TasksTable", skip_lines=1)
        return _md_style(_TABLE_CSS) + markdown.markdown(content, extensions=['tables'])

    def _buildChangelogDoc(self):
        content = self._read_doc("Changelog", skip_lines=1)
        return _md_style(_LINK_CSS) + markdown.markdown(content).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

    def retranslateUi(self):
        StyleSheet.HELP_INTERFACE.apply(self)
        self.helpLabel.setText(tr('帮助'))
        self.helpLabel.adjustSize()
        self.websiteButton.setText(tr('在官网查看'))
        self.websiteButton.adjustSize()
        self.websiteButton.move(self.width() - self.websiteButton.width() - 36, 36)
        labels = [tr('使用教程'), tr('流程编排'), tr('常见问题'),
                  tr('后台运行'), tr('每日实训'), tr('更新日志')]
        positions = {}
        for attr, text in zip(DOC_OF_TAB, labels):
            self.pivot.items[attr].setText(text)
            positions[attr] = getattr(self, attr).verticalScrollBar().value()
        self.pivot.adjustSize()
        # 语言变了文档路径也变了：重新渲染已打开过的标签页，未打开过的留待首次切换时渲染。
        rebuild = [name for name in DOC_OF_TAB if name in self._builtDocs]
        self._builtDocs.clear()
        self._docContent.clear()
        for name in rebuild:
            self._ensureDocBuilt(name)
        for attr, position in positions.items():
            getattr(self, attr).verticalScrollBar().setValue(position)

    def __initLayout(self):
        self.helpLabel.move(36, 30)
        self.pivot.move(40, 80)

        self.stackedWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.vBoxLayout.addWidget(self.stackedWidget, 1)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        # self.vBoxLayout.addWidget(self.tutorialLabel, 0, Qt.AlignTop)
        self.addSubInterface(self.tutorialLabel, 'tutorialLabel', tr('使用教程'))
        self.addSubInterface(self.workflowLabel, 'workflowLabel', tr('流程编排'))
        self.addSubInterface(self.faqLabel, 'faqLabel', tr('常见问题'))
        self.addSubInterface(self.backgroundLabel, 'backgroundLabel', tr('后台运行'))
        self.addSubInterface(self.tasksLabel, 'tasksLabel', tr('每日实训'))
        self.addSubInterface(self.changelogLabel, 'changelogLabel', tr('更新日志'))

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())

    def addSubInterface(self, widget: TextBrowser, objectName, text):
        widget.setObjectName(objectName)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.document().setDocumentMargin(10)

        custom_scrollbar_qss = """
            QTextBrowser {
                background: transparent;
                border: none;
                selection-background-color: #f18cb9;
            }
            QTextBrowser:hover {
                background: transparent;
                border: none;
                selection-background-color: #f18cb9;
            }
            QTextBrowser:focus {
                background: transparent;
                border: none;
                selection-background-color: #f18cb9;
            }
            
            QScrollBar:vertical {
                background: transparent;
                width: 12px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 150);
                border-radius: 5px;
                border-width: 1px;
                width: 10px;
                min-height: 30px;
                margin: 2px 1px 2px 1px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: rgba(128, 128, 128, 200);
                border-radius: 5px;
            }
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }
            
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """
        setCustomStyleSheet(widget, custom_scrollbar_qss, custom_scrollbar_qss)

        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())
        # 首次切换到该页时才渲染它的文档。
        self._ensureDocBuilt(widget.objectName())

        self.verticalScrollBar().setValue(0)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def openWebsite(self):
        doc = os.path.splitext(os.path.basename(
            self._get_localized_doc_path(DOC_OF_TAB[self.stackedWidget.currentWidget().objectName()])))[0]
        self.open_url(f'https://m7a.top/docs/#/assets/docs/{doc}')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 按钮与标题同一行、靠右对齐（右边距与左侧 36px 对称）
        self.websiteButton.move(self.width() - self.websiteButton.width() - 36, 36)

    @staticmethod
    def _site_links(text: str) -> str:
        """文档里的站内链接（/assets/docs/X.md）换成官网文档地址，界面中才能直接打开。"""
        return re.sub(r'\]\(/assets/docs/(\w+)\.md\)', r'](https://m7a.top/docs/#/assets/docs/\1)', text)

    def _get_localized_doc_path(self, base_name: str) -> str:
        from module.localization.languages import localized_doc_path
        return localized_doc_path(base_name)

    def __themeChanged(self):
        # 只重设已经渲染过的标签页，未渲染的会在首次打开时按当时主题生成。
        for name in list(self._builtDocs):
            self._applyDoc(name)
