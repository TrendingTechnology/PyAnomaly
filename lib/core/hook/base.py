import os
import pickle
import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader
from collections import OrderedDict
import matplotlib.pyplot as plt
from tsnecuda import TSNE
from scipy.ndimage import gaussian_filter1d

from .abstract.abstract_hook import HookBase
from lib.datatools.evaluate.utils import psnr_error
from lib.datatools.evaluate.gtloader import GroundTruthLoader
# from lib.datatools.evaluate import eval_api
from lib.core.utils import tsne_vis

HOOKS = ['VisScoreHook', 'TSNEHook']

class VisScoreHook(HookBase):
    def after_step(self, current_step):
        writer = self.trainer.kwargs['writer_dict']['writer']
        global_steps = self.trainer.kwargs['writer_dict']['global_steps_{}'.format(self.trainer.kwargs['model_type'])]

        if not os.path.exists(self.trainer.config.LOG.vis_dir):
            os.mkdir(self.trainer.config.LOG.vis_dir)
        
        if current_step % self.trainer.config.TRAIN.eval_step == 0 and current_step != 0:
            result_path = os.path.join(self.trainer.config.TEST.result_output, f'{self.trainer.verbose}_cfg#{self.trainer.config_name}#step{current_step}@{self.trainer.kwargs["time_stamp"]}_results.pkl')
            with open(result_path, 'rb') as reader:
                results = pickle.load(reader)
            
            psnrs = results['psnr']
            scores = results['score']
            gt_loader = GroundTruthLoader(self.trainer.config)
            gt = gt_loader()
            if psnrs == []:
                for i in range(len(scores)):
                    psnrs.append(np.zeros(shape=(scores[i].shape[0],)))
            elif scores == []:
                for i in range(len(psnrs)):
                    scores.append(np.zeros(shape=(psnrs[i].shape[0],)))
            else:
                assert len(psnrs) == len(scores), 'the number of psnr and score is not equal'
            
            assert len(gt) == len(psnrs) == len(scores), f'the number of gt {len(gt)}, psnrs {len(psnrs)}, scores {len(scores)}'
            
            # plt the figure
            for video_id in range(len(psnrs)):
                assert len(psnrs[video_id]) == len(scores[video_id]) == len(gt[video_id]), f'video_id:{video_id},the number of gt {len(gt)}, psnrs {len(psnrs)}, scores {len(scores)}'
                fig = plt.figure()
                fig.tight_layout()
                fig.subplots_adjust(wspace=0.4)
                ax1 = fig.add_subplot(2,2,1)
                ax1.plot([i for i in range(len(psnrs[video_id]))], psnrs[video_id])
                ax1.set_ylabel('psnr')
                ax2 = fig.add_subplot(2,2,2)
                ax2.plot([i for i in range(len(scores[video_id]))], scores[video_id])
                ax2.set_ylabel('score')
                ax3 = fig.add_subplot(2,2,3)
                ax3.plot([i for i in range(len(gt[video_id]))], gt[video_id])
                ax3.set_ylabel('GT')
                ax3.set_xlabel('frames')
                ax4 = fig.add_subplot(2,2,4)
                # import ipdb; ipdb.set_trace()
                if self.trainer.config.DATASET.smooth.guassian:
                    smooth_score = gaussian_filter1d(scores[video_id], self.trainer.config.DATASET.smooth.guassian_sigma)
                else:
                    smooth_score = scores[video_id]
                ax4.plot([i for i in range(len(smooth_score))], smooth_score)
                ax4.set_ylabel(f'Guassian Smooth{self.trainer.config.DATASET.smooth.guassian_sigma}')
                ax4.set_xlabel('frames')
                writer.add_figure(f'verbose_{self.trainer.verbose}_{self.trainer.config_name}_{self.trainer.kwargs["time_stamp"]}_vis{video_id}', fig, global_steps)
                # plt.savefig(vis_path)
            
        
            self.trainer.logger.info(f'^^^^Finish vis @{current_step}')

class TSNEHook(HookBase):
    def after_step(self, current_step):
        writer = self.trainer.kwargs['writer_dict']['writer']
        global_steps = self.tainer.kwargs['writer_dict']['global_steps_{}'.format(self.kwargs['model_type'])]

        if not os.path.exists(self.trainer.config.LOG.vis_dir):
            os.mkdir(self.trainer.config.LOG.vis_dir)
        
        if current_step % self.trainer.config.TRAIN.eval_step == 0:
            vis_path = os.path.join(self.trainer.config.LOG.vis_dir, f'{self.trainer.config.DATASET.name}_tsne_model:{self.trainer.config.MODEL.name}_step:{current_step}.jpg')
            feature, feature_labels = self.trainer.analyze_feature
            tsne_vis(feature, feature_labels, vis_path)
            image = cv2.imread(vis_path)
            image = image[:,:,[2,1,0]]
            writer.add_image(str(vis_path), image, global_step=global_steps)


def get_base_hooks(name):
    if name in HOOKS:
        t = eval(name)()
    else:
        raise Exception('The hook is not in amc_hooks')
    return t

        
