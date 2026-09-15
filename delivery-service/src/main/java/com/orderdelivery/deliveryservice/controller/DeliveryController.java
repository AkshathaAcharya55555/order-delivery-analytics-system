package com.orderdelivery.deliveryservice.controller;

import com.orderdelivery.deliveryservice.dto.DeliveryResponse;
import com.orderdelivery.deliveryservice.dto.UpdateDeliveryStatusRequest;
import com.orderdelivery.deliveryservice.service.DeliveryService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/deliveries")
public class DeliveryController {

    private final DeliveryService deliveryService;

    public DeliveryController(DeliveryService deliveryService) {
        this.deliveryService = deliveryService;
    }

    @PostMapping("/{orderId}/assign")
    public ResponseEntity<DeliveryResponse> assign(@PathVariable Long orderId) {
        var delivery = deliveryService.assignRider(orderId);
        return ResponseEntity.status(HttpStatus.CREATED).body(DeliveryResponse.from(delivery));
    }

    @PutMapping("/{orderId}/status")
    public DeliveryResponse updateStatus(@PathVariable Long orderId, @Valid @RequestBody UpdateDeliveryStatusRequest request) {
        return DeliveryResponse.from(deliveryService.updateStatus(orderId, request.getStatus()));
    }

    @GetMapping("/{orderId}")
    public DeliveryResponse get(@PathVariable Long orderId) {
        return DeliveryResponse.from(deliveryService.getByOrderId(orderId));
    }
}
