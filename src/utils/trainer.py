import wandb
import segmentation_models_pytorch as smp
from .train_utils import TrainEpoch, ValidEpoch
from .loss import custom_loss
from .dataloader import Dataset
from .transformations import get_training_augmentation, get_validation_augmentation, get_preprocessing
from .model import Unet
from torchmetrics import StructuralSimilarityIndexMeasure
from torchmetrics import PeakSignalNoiseRatio
import torch
from torch.utils.data import DataLoader
def train_model(encoder='resnet34', encoder_weights='imagenet', device='cuda', lr=1e-4):
    
    wandb.init(project="ThermalSuperResolutionN", entity="kasliwal17",
               config={'model':'resnet152 d5','fusion_technique':'img 2 encoders decoder-attention avg tanh x+p/10+z/100+y/10 saving:ssim',
                'lr':lr, 'max_ssim':0, 'max_psnr':0})

    activation = 'tanh' 
    # create segmentation model with pretrained encoder
    model = Unet(
        encoder_name=encoder, 
        encoder_weights=encoder_weights, 
        encoder_depth = 5,
        classes=1, 
        activation=activation,
        fusion=True,
        contrastive=True,
        decoder_attention_type='scse',
    )

    preprocessing_fn = smp.encoders.get_preprocessing_fn(ENCODER, ENCODER_WEIGHTS)


    train_dataset = Dataset(
        inputs1_train,
        inputs2_train,
        targets_train,
        augmentation=get_training_augmentation(), 
        preprocessing=get_preprocessing(preprocessing_fn)
    )
    valid_dataset = Dataset(
        inputs1_valid,
        inputs2_valid,
        targets_valid,
        augmentation=get_validation_augmentation(), 
        preprocessing=get_preprocessing(preprocessing_fn)
    )
    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True)
    valid_loader = DataLoader(valid_dataset, batch_size=4, shuffle=True, drop_last=True)

    loss = custom_loss()
    Z = StructuralSimilarityIndexMeasure()
    P = PeakSignalNoiseRatio()
    P.__name__ = 'psnr'
    Z.__name__ = 'ssim'
    metrics = [
        Z,
        P,
    ]

    learning_rate=1e-4##set learning rate here
    optimizer = torch.optim.Adam([ 
        dict(params=model.parameters(), lr=learning_rate),
    ])

    train_epoch = TrainEpoch(
        model, 
        loss=loss, 
        metrics=metrics, 
        optimizer=optimizer,
        device=device,
        verbose=True,
        contrastive=True
    )
    valid_epoch = ValidEpoch(
        model, 
        loss=loss, 
        metrics=metrics, 
        device=device,
        verbose=True,
        contrastive=True
    )

    max_ssim = 0
    max_psnr = 0
    counter = 0
    epochs=250
    for i in range(0, epochs):
        
        print('\nEpoch: {}'.format(i))
        train_logs = train_epoch.run(train_loader)
        valid_logs = valid_epoch.run(valid_loader)
        print(train_logs)
        wandb.log({'epoch':i+1,'t_loss':train_logs['custom_loss'],'t_ssim':train_logs['ssim'],'v_loss':valid_logs['custom_loss'],'v_ssim':valid_logs['ssim']})
        # do something (save model, change lr, etc.)
        if max_ssim <= valid_logs['ssim']:
            max_ssim = valid_logs['ssim']
            max_psnr = valid_logs['psnr']
            wandb.config.max_ssim = max_ssim
            wandb.config.max_psnr = max_psnr
            torch.save(model.state_dict(), './best_model.pth')
            print('Model saved!')
            counter = 0
        counter = counter+1