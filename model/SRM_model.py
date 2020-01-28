
import numpy as np
import torch
import torch.nn as nn
import torchvision


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
                               padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class Stage1(nn.Module):

    def __init__(self, block, layers):
        super().__init__()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)

        self.conv6 = nn.Conv2d(2048, 256, 3, padding=1)
        self.conv7 = nn.Conv2d(256, 2, 3, padding=1)

        self._copy_params()

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.conv6(x)
        x = self.conv7(x)

        return x

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def _copy_params(self):
        pretrained_dict = torchvision.models.resnet50(
            pretrained=True).state_dict()
        model_dict = self.state_dict()
        pretrained_dict = {
            k: v for k,
            v in pretrained_dict.items() if k in model_dict}
        model_dict.update(pretrained_dict)
        self.load_state_dict(model_dict)
        del pretrained_dict


class Stage2(nn.Module):

    def __init__(self, block, layers):
        super().__init__()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.ppm = PPM()

        self._copy_params()

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.ppm(x)

        return x

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def _copy_params(self):
        pretrained_dict = torchvision.models.resnet50(
            pretrained=True).state_dict()
        model_dict = self.state_dict()
        pretrained_dict = {
            k: v for k,
            v in pretrained_dict.items() if k in model_dict}
        model_dict.update(pretrained_dict)
        self.load_state_dict(model_dict)


class PPM(nn.Module):

    def __init__(self):
        super().__init__()
        self.block1 = nn.Sequential(  # 1*1 bin
            nn.AvgPool2d(24, stride=24),
            nn.Conv2d(1024, 512, 1),
        )

        self.block2 = nn.Sequential(  # 2*2 bins
            nn.AvgPool2d(12, stride=12),
            nn.Conv2d(1024, 512, 1)
        )

        self.block3 = nn.Sequential(  # 3*3 bins
            nn.AvgPool2d(8, stride=8),
            nn.Conv2d(1024, 512, 1)
        )

        self.block4 = nn.Sequential(  # 6*6 bins
            nn.AvgPool2d(4, stride=4),
            nn.Conv2d(1024, 512, 1)
        )

    def forward(self, x):  # x shape: 24*24
        x1 = self.block1(x)
        x1 = nn.functional.interpolate(x1, size=24, mode='bilinear', align_corners=True)
        x2 = self.block2(x)
        x2 = nn.functional.interpolate(x2, size=24, mode='bilinear', align_corners=True)
        x3 = self.block3(x)
        x3 = nn.functional.interpolate(x3, size=24, mode='bilinear', align_corners=True)
        x4 = self.block4(x)
        x4 = nn.functional.interpolate(x4, size=24, mode='bilinear', align_corners=True)
        output = torch.cat([x, x1, x2, x3, x4], 1)
        return output


class SRM(nn.Module):

    def __init__(self):
        super().__init__()
        self.stage1 = Stage1(Bottleneck, [3, 4, 6, 3])
        self.stage2 = Stage2(Bottleneck, [3, 4, 6, 3])
        self.conv1 = nn.Conv2d(3072, 256, 3, padding=1)
        self.conv2 = nn.Conv2d(256, 64, 3, padding=1)
        self.conv6 = nn.Conv2d(66, 256, 3, padding=1)
        self.conv7 = nn.Conv2d(256, 2, 3, padding=1)

    def forward(self, x):
        feature1 = self.stage1(x)
        output1 = nn.functional.interpolate(feature1, size=384, mode='bilinear', align_corners=True)
        feature2 = self.stage2(x)
        feature2 = self.conv1(feature2)
        feature2 = self.conv2(feature2)
        feature1 = nn.functional.interpolate(feature1, size=24, mode='bilinear', align_corners=True)
        feature = torch.cat([feature1, feature2], 1)
        feature = self.conv6(feature)
        feature = self.conv7(feature)
        output2 = nn.functional.interpolate(feature, size=384, mode='bilinear', align_corners=True)

        return output1, output2


if __name__ == '__main__':
    imgs = torch.ones(1, 3, 384, 384)
    model = SRM()
    output1, output2 = model.forward(imgs)
