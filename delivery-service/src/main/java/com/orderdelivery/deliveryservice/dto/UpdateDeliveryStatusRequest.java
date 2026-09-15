package com.orderdelivery.deliveryservice.dto;

import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import jakarta.validation.constraints.NotNull;

public class UpdateDeliveryStatusRequest {

    @NotNull
    private DeliveryStatus status;

    public DeliveryStatus getStatus() {
        return status;
    }

    public void setStatus(DeliveryStatus status) {
        this.status = status;
    }
}
