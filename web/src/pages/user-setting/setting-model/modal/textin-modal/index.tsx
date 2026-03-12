import { RAGFlowFormItem } from '@/components/ragflow-form';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Form } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { LLMFactory } from '@/constants/llm';
import { VerifyResult } from '@/pages/user-setting/setting-model/hooks';
import { zodResolver } from '@hookform/resolvers/zod';
import { t } from 'i18next';
import { memo } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { LLMHeader } from '../../components/llm-header';
import VerifyButton from '../verify-button';

const FormSchema = z.object({
  llm_name: z.string().min(1, {
    message: t('setting.textin.modelNameRequired'),
  }),
  textin_api_url: z.string().optional().default('https://api.textin.com/ai/service/v1/pdf_to_markdown'),
  textin_app_id: z.string().optional(),
  textin_secret_code: z.string().optional(),
});

export type TextInFormValues = z.infer<typeof FormSchema>;

export interface IModalProps<T> {
  visible: boolean;
  hideModal: () => void;
  onOk?: (data: T) => Promise<boolean>;
  onVerify?: (
    postBody: any,
  ) => Promise<boolean | void | VerifyResult | undefined>;
  loading?: boolean;
}

const TextInModal = ({
  visible,
  hideModal,
  onOk,
  onVerify,
  loading,
}: IModalProps<TextInFormValues>) => {
  const { t } = useTranslation();

  const form = useForm<TextInFormValues>({
    resolver: zodResolver(FormSchema),
    defaultValues: {
      textin_api_url: 'https://api.textin.com/ai/service/v1/pdf_to_markdown',
    },
  });

  const handleOk = async (values: TextInFormValues) => {
    const ret = await onOk?.(values as any);
    if (ret) {
      hideModal?.();
    }
  };

  return (
    <Dialog open={visible} onOpenChange={hideModal}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <LLMHeader name={LLMFactory.TextIn} />
          </DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleOk)}
            className="space-y-6"
            id="textin-form"
          >
            <RAGFlowFormItem
              name="llm_name"
              label={t('setting.modelName')}
              required
            >
              <Input
                placeholder={t('setting.textin.modelNamePlaceholder', 'Enter a name for this TextIn configuration')}
              />
            </RAGFlowFormItem>
            <RAGFlowFormItem
              name="textin_api_url"
              label={t('setting.textin.apiUrl', 'TextIn API URL')}
            >
              <Input
                placeholder={t('setting.textin.apiUrlPlaceholder', 'https://api.textin.com/ai/service/v1/pdf_to_markdown')}
              />
            </RAGFlowFormItem>
            <RAGFlowFormItem
              name="textin_app_id"
              label={t('setting.textin.appId', 'App ID')}
            >
              <Input
                placeholder={t('setting.textin.appIdPlaceholder', 'Enter your TextIn App ID')}
              />
            </RAGFlowFormItem>
            <RAGFlowFormItem
              name="textin_secret_code"
              label={t('setting.textin.secretCode', 'Secret Code')}
            >
              <Input
                type="password"
                placeholder={t('setting.textin.secretCodePlaceholder', 'Enter your TextIn Secret Code')}
              />
            </RAGFlowFormItem>
            {onVerify && (
              <VerifyButton
                onVerify={onVerify as (postBody: any) => Promise<VerifyResult>}
              />
            )}
            <DialogFooter>
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={hideModal}
                  className="btn btn-secondary"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn btn-primary"
                >
                  {t('common.add')}
                </button>
              </div>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export default memo(TextInModal);