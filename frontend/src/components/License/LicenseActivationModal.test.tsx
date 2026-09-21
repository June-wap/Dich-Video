import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { LicenseActivationModal } from './LicenseActivationModal';
import { licenseService } from '../../services/licenseService';
import { ApiError, NetworkError } from '../../services/httpClient';

vi.mock('../../services/licenseService', () => ({
  licenseService: {
    activate: vi.fn(),
  },
}));

describe('LicenseActivationModal error handling', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    statusData: {
      status: 'UNLICENSED' as const,
      is_active: false,
      machine_id: 'TEST-MACHINE-1234',
      message: 'Chưa có bản quyền',
    },
    onActivated: vi.fn(),
  };

  it('displays precise local backend failure message on NetworkError', async () => {
    const user = userEvent.setup();
    vi.mocked(licenseService.activate).mockRejectedValueOnce(
      new NetworkError('Failed to fetch')
    );

    render(<LicenseActivationModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText(/Dán mã kích hoạt bản quyền/i);
    await user.type(textarea, 'VB-TEST-KEY-1234');

    const activateBtn = screen.getByRole('button', { name: 'Kích hoạt ngay' });
    await user.click(activateBtn);

    await waitFor(() => {
      expect(
        screen.getByText(
          /Không thể kết nối dịch vụ Voca Basic cục bộ\. Vui lòng đóng và mở lại ứng dụng\./i
        )
      ).toBeInTheDocument();
    });
  });

  it('preserves specific ApiError message without masking it', async () => {
    const user = userEvent.setup();
    vi.mocked(licenseService.activate).mockRejectedValueOnce(
      new ApiError('LICENSE_EXPIRED', 'Mã bản quyền này đã hết hạn sử dụng.', 403)
    );

    render(<LicenseActivationModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText(/Dán mã kích hoạt bản quyền/i);
    await user.type(textarea, 'VB-EXPIRED-KEY-999');

    const activateBtn = screen.getByRole('button', { name: 'Kích hoạt ngay' });
    await user.click(activateBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Mã bản quyền này đã hết hạn sử dụng\./i)
      ).toBeInTheDocument();
    });
  });
});
