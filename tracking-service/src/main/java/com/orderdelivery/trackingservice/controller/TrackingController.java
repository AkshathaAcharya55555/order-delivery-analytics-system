package com.orderdelivery.trackingservice.controller;

import com.orderdelivery.trackingservice.dto.AddTrackingEventRequest;
import com.orderdelivery.trackingservice.dto.TrackingEventResponse;
import com.orderdelivery.trackingservice.dto.TrackingResponse;
import com.orderdelivery.trackingservice.service.TrackingService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/orders/{orderId}/tracking")
public class TrackingController {

    private final TrackingService trackingService;

    public TrackingController(TrackingService trackingService) {
        this.trackingService = trackingService;
    }

    @GetMapping
    public TrackingResponse getTracking(@PathVariable Long orderId) {
        String currentStatus = trackingService.getCurrentStatus(orderId); // Redis cache-aside, Postgres fallback
        List<TrackingEventResponse> history = trackingService.getHistory(orderId).stream()
                .map(TrackingEventResponse::from)
                .collect(Collectors.toList());
        return new TrackingResponse(orderId, currentStatus, history);
    }

    /**
     * Not explicitly requested as a named endpoint in the original spec, but
     * necessary to fulfil "store complete status history" / "validate
     * invalid status transitions" for the CONFIRMED/PREPARING/READY_FOR_PICKUP
     * stages, which no other service's endpoints reach. See README.
     */
    @PostMapping
    public ResponseEntity<TrackingEventResponse> addEvent(@PathVariable Long orderId,
                                                            @Valid @RequestBody AddTrackingEventRequest request) {
        var event = trackingService.addTrackingEvent(orderId, request.getStatus());
        return ResponseEntity.status(HttpStatus.CREATED).body(TrackingEventResponse.from(event));
    }
}
