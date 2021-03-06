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
from lib.datatools.evaluate.utils import reconstruction_loss
from lib.datatools.evaluate.gtloader import GroundTruthLoader
# from lib.datatools.evaluate import eval_api
from lib.core.utils import tsne_vis

HOOKS = ['STAEEvaluateHook']

class STAEEvaluateHook(HookBase):
    def after_step(self, current_step):
        acc = 0.0
        if current_step % self.trainer.eval_step == 0 and current_step != 0:
            with torch.no_grad():
                acc = self.evaluate(current_step)
                if acc > self.trainer.accuarcy:
                    self.trainer.accuarcy = acc
                    # save the model & checkpoint
                    self.trainer.save(current_step, best=True)
                elif current_step % self.trainer.save_step == 0 and current_step != 0:
                    # save the checkpoint
                    self.trainer.save(current_step)
                    self.trainer.logger.info('LOL==>the accuracy is not imporved in epcoh{} but save'.format(current_step))
                else:
                    pass
        else:
            pass
    
    def inference(self):
        # import ipdb; ipdb.set_trace()
        acc = self.evaluate(0)
        self.trainer.logger.info(f'The inference metric is:{acc:.3f}')
    
    def evaluate(self, current_step):
        '''
        Evaluate the results of the model
        !!! Will change, e.g. accuracy, mAP.....
        !!! Or can call other methods written by the official
        '''
        tb_writer = self.trainer.kwargs['writer_dict']['writer']
        global_steps = self.trainer.kwargs['writer_dict']['global_steps_{}'.format(self.trainer.kwargs['model_type'])]
        frame_num = self.trainer.config.DATASET.test_clip_length
        clip_step = self.trainer.config.DATASET.test_clip_step
        psnr_records=[]
        score_records=[]
        # total = 0
        num_videos = 0
        random_video_sn = torch.randint(0, len(self.trainer.test_dataset_keys), (1,))
        # calc the score for the test dataset
        for sn, video_name in enumerate(self.trainer.test_dataset_keys):
            num_videos += 1
            # need to improve
            dataset = self.trainer.test_dataset_dict[video_name]
            len_dataset = dataset.pics_len
            # test_iters = len_dataset - frame_num + 1
            test_iters = len_dataset // clip_step
            test_counter = 0

            data_loader = DataLoader(dataset=dataset, batch_size=1, shuffle=False, num_workers=1)
            vis_range = range(int(len_dataset*0.5), int(len_dataset*0.5 + 5))
            # scores = np.empty(shape=(len_dataset,),dtype=np.float32)
            scores = torch.zeros(len_dataset)
            # scores = [0.0 for i in range(len_dataset)]
            for clip_sn, test_input in enumerate(data_loader):
                test_target = test_input.cuda()
                time_len = test_input.shape[2]
                output, pred = self.trainer.STAE(test_target)
                clip_score = reconstruction_loss(output, test_target)
                # score = np.array(score.tolist() * time_len)
                if len_dataset < (test_counter+1) * time_len:
                    # import ipdb; ipdb.set_trace()
                    clip_score = clip_score[:,0:len_dataset-(test_counter)*time_len]
                if len(clip_score.shape) >= 2:
                    clip_score = clip_score.sum(dim=0)
                try:
                    scores[test_counter*time_len:(test_counter + 1)*time_len] = clip_score.squeeze(0)
                except:
                    import ipdb; ipdb.set_trace()
                
                # scores[test_counter+frame_num-1] = score
                # import ipdb; ipdb.set_trace()
                test_counter += 1

                if sn == random_video_sn and (clip_sn in vis_range):
                    self.add_images(test_target, output, tb_writer, global_steps)
                
                if test_counter >= test_iters:
                    # import ipdb; ipdb.set_trace()
                    # import ipdb; ipdb.set_trace()
                    # scores[:frame_num-1]=(scores[frame_num-1],) # fix the bug: TypeError: can only assign an iterable
                    smax = max(scores)
                    smin = min(scores)
                    # normal_scores = np.array([(1.0 - np.divide(s-smin, smax)) for s in scores])
                    normal_scores = (1.0 - torch.div(scores-smin, smax)).detach().cpu().numpy()
                    score_records.append(normal_scores)
                    print(f'finish test video set {video_name}')
                    break
        
        result_dict = {'dataset': self.trainer.config.DATASET.name, 'psnr': psnr_records, 'flow': [], 'names': [], 'diff_mask': [], 'score':score_records, 'num_videos':num_videos}
        result_path = os.path.join(self.trainer.config.TEST.result_output, f'{self.trainer.verbose}_cfg#{self.trainer.config_name}#step{current_step}@{self.trainer.kwargs["time_stamp"]}_results.pkl')
        with open(result_path, 'wb') as writer:
            pickle.dump(result_dict, writer, pickle.HIGHEST_PROTOCOL)
        
        results = self.trainer.evaluate_function(result_path, self.trainer.logger, self.trainer.config, self.trainer.config.DATASET.score_type)
        self.trainer.logger.info(results)
        tb_writer.add_text('amc: AUC of ROC curve', f'auc is {results.auc}',global_steps)
        return results.auc

    def add_images(self, clip, clip_hat, writer, global_steps):
        clip = self.verse_normalize(clip.detach())
        clip_hat = self.verse_normalize(clip_hat.detach())
        
        writer.add_images('eval_clip', clip, global_steps)
        writer.add_images('eval_clip_hat', clip_hat, global_steps)
    
    def verse_normalize(self, image_tensor):
        std = self.trainer.config.ARGUMENT.val.normal.std
        mean = self.trainer.config.ARGUMENT.val.normal.mean
        if len(mean) == 0 and len(std) == 0:
            return image_tensor
        else:
            for i in range(len(std)):
                image_tensor[:,i,:,:] = image_tensor[:,i,:,:] * std[i] + mean[i]
            return image_tensor


def get_stae_hooks(name):
    if name in HOOKS:
        t = eval(name)()
    else:
        raise Exception('The hook is not in amc_hooks')
    return t