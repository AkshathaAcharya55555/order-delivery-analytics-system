package com.orderdelivery.deliveryservice.controller;

import com.orderdelivery.deliveryservice.dto.CreateRiderRequest;
import com.orderdelivery.deliveryservice.dto.RiderAvailabilityResponse;
import com.orderdelivery.deliveryservice.dto.RiderResponse;
import com.orderdelivery.deliveryservice.dto.UpdateAvailabilityRequest;
import com.orderdelivery.deliveryservice.service.RiderService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/riders")
public class RiderController {

    private final RiderService riderService;

    public RiderController(RiderService riderService) {
        this.riderService = riderService;
    }

    @PostMapping
    public ResponseEntity<RiderResponse> createRider(@Valid @RequestBody CreateRiderRequest request) {
        var rider = riderService.createRider(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(RiderResponse.from(rider));
    }

    @GetMapping
    public Page<RiderResponse> listRiders(Pageable pageable) {
        return riderService.listRiders(pageable).map(RiderResponse::from);
    }

    @PutMapping("/{id}/availability")
    public RiderResponse updateAvailability(@PathVariable Long id, @Valid @RequestBody UpdateAvailabilityRequest request) {
        return RiderResponse.from(riderService.updateAvailability(id, request.getAvailable()));
    }

    /** Cache-aside read (Redis, Postgres fallback) — see RiderAvailabilityCache. */
    @GetMapping("/{id}/availability")
    public RiderAvailabilityResponse getAvailability(@PathVariable Long id) {
        return new RiderAvailabilityResponse(id, riderService.getAvailability(id));
    }
}
