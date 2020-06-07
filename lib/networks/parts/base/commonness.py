import torch
import torch.nn as nn
import torchsnooper
import torch.nn.functional as F
class BasicConv2d(nn.Module):
    '''
    The basic convaolution with bn
    '''
    def __init__(self, in_channels, out_channels, **kwargs):
        super(BasicConv2d, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, bias=True, **kwargs)
        self.bn = nn.BatchNorm2d(out_channels, eps=0.001)
    
    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        # return F.relu(x, inplace=True)
        return x 

class Conv2dLeakly(nn.Module):
    '''
    The basic convolution with leakly relu
    '''
    def __init__(self, c_in, c_out, bn_flag=True, **kwargs):
        super(Conv2dLeakly, self).__init__()
        self.bn_flag = bn_flag
        self.conv = nn.Conv2d(c_in, c_out, **kwargs)
        
        self.bn = nn.BatchNorm2d(c_out)
    # @torchsnooper.snoop()
    def forward(self,x):
        x = self.conv(x)
        if self.bn_flag:
            x = self.bn(x)
        return F.leaky_relu_(x)

class ConcatDeconv2d(nn.Module):
    def __init__(self, c_in, c_out, dropout_prob):
        '''
        use the conv_tranpose to enlarge the feature into two times
        '''
        super(ConcatDeconv2d, self).__init__()
        self.conv_transpose = nn.ConvTranspose2d(c_in, c_out, kernel_size=4, stride=2, padding=1)
        self.bn = nn.BatchNorm2d(c_out)
        self.dropout = nn.Dropout2d(p=dropout_prob)
        self.reduce_channel = nn.Conv2d(c_out*2, c_out, kernel_size=1)
    def forward(self, x1, x2):
        x1 = self.conv_transpose(x1)
        x1 = self.dropout(x1)
        x1 = F.relu_(x1)
        x2 = torch.cat([x1,x2], dim=1)
        x2 = self.reduce_channel(x2)
        # import ipdb; ipdb.set_trace()
        return x2

class Deconv2d(nn.Module):
    def __init__(self, c_in, c_out, dropout_prob):
        '''
        use the conv_tranpose to enlarge the feature into two times
        '''
        super(Deconv2d, self).__init__()
        self.conv_transpose = nn.ConvTranspose2d(c_in, c_out, kernel_size=(4,4), stride=2, padding=1)
        self.bn = nn.BatchNorm2d(c_out)
        self.dropout = nn.Dropout2d(p=dropout_prob)
    
    def forward(self,x):
        x = self.conv_transpose(x)
        x = self.dropout(x)

        return F.relu_(x)

class Inception(nn.Module):
    def __init__(self, c_in, c_out, max_filter_size=7):
        super(Inception, self).__init__()
        assert max_filter_size % 2 == 1 and max_filter_size < 8
        self.n_branch = (max_filter_size + 1 ) // 2
        assert c_out % self.n_branch == 0
        nf_branch = c_out // self.n_branch
        # 1x1 
        self.branch1 = BasicConv2d(in_channels=c_in, out_channels=nf_branch, kernel_size=1)
        # 3x3
        self.branch2 = Inception3x3(in_channels=c_in, out_channels=nf_branch)
        # 5x5
        self.branch3 = Inception5x5(in_channels=c_in, out_channels=nf_branch)
        # 7x7
        self.branch4 = Inception7x7(in_channels=c_in, out_channels=nf_branch)

    def forward(self, x):
        out1 = self.branch1(x)
        if self.n_branch == 1:
            return out1
        out2 = self.branch2(x)
        if self.n_branch == 2:
            return torch.cat([out1, out2], dim=1)
        out3 = self.branch3(x)
        if self.n_branch == 3:
            return torch.cat([out1, out2, out3], dim=1)
        out4 = self.branch4(x)
        if self.n_branch == 4:
            return torch.cat([out1, out2, out3, out4], dim=1)

        # return x
        

class Inception3x3(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Inception3x3, self).__init__()
        self.s3_11 = BasicConv2d(in_channels, out_channels, kernel_size=1)
        self.s3_1n = BasicConv2d(out_channels, out_channels, kernel_size=(1,3), padding=(0,1))
        self.s3_n1 = BasicConv2d(out_channels, out_channels, kernel_size=(3,1), padding=(1,0))
    
    def forward(self,x):
        x = self.s3_11(x)
        x = self.s3_1n(x)
        x = self.s3_n1(x)

        return x

class Inception5x5(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Inception5x5, self).__init__()
        self.s5_11 = BasicConv2d(in_channels, out_channels, kernel_size=1)
        self.s5_1n_a = BasicConv2d(out_channels, out_channels, kernel_size=(1,3), padding=(0,1))
        self.s5_n1_a = BasicConv2d(out_channels, out_channels, kernel_size=(3,1), padding=(1,0))
        self.s5_1n_b = BasicConv2d(out_channels, out_channels, kernel_size=(1,3), padding=(0,1))
        self.s5_n1_b = BasicConv2d(out_channels, out_channels, kernel_size=(3,1), padding=(1,0))
    
    def forward(self,x):
        x = self.s5_11(x)
        x = self.s5_1n_a(x)
        x = self.s5_n1_a(x)
        x = self.s5_1n_b(x)
        x = self.s5_n1_b(x)

        return x
class Inception7x7(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Inception7x7, self).__init__()
        self.s7_11 = BasicConv2d(in_channels, out_channels, kernel_size=1)
        self.s7_1n_a = BasicConv2d(out_channels, out_channels, kernel_size=(1,3), padding=(0,1))
        self.s7_n1_a = BasicConv2d(out_channels, out_channels, kernel_size=(3,1), padding=(1,0))
        self.s7_1n_b = BasicConv2d(out_channels, out_channels, kernel_size=(1,3), padding=(0,1))
        self.s7_n1_b = BasicConv2d(out_channels, out_channels, kernel_size=(3,1), padding=(1,0))
        self.s7_1n_c = BasicConv2d(out_channels, out_channels, kernel_size=(1,3), padding=(0,1))
        self.s7_n1_c = BasicConv2d(out_channels, out_channels, kernel_size=(3,1), padding=(1,0))
    
    def forward(self, x):
        x = self.s7_11(x)
        x = self.s7_1n_a(x)
        x = self.s7_n1_a(x)
        x = self.s7_1n_b(x)
        x = self.s7_n1_b(x)
        x = self.s7_1n_c(x)
        x = self.s7_n1_c(x)

        return x