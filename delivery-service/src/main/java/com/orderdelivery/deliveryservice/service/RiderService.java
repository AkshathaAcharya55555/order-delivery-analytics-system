package com.orderdelivery.deliveryservice.service;

import com.orderdelivery.deliveryservice.cache.RiderAvailabilityCache;
import com.orderdelivery.deliveryservice.dto.CreateRiderRequest;
import com.orderdelivery.deliveryservice.entity.Rider;
import com.orderdelivery.deliveryservice.exception.ResourceNotFoundException;
import com.orderdelivery.deliveryservice.repository.RiderRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;

@Service
public class RiderService {

    private final RiderRepository riderRepository;
    private final RiderAvailabilityCache availabilityCache;

    public RiderService(RiderRepository riderRepository, RiderAvailabilityCache availabilityCache) {
        this.riderRepository = riderRepository;
        this.availabilityCache = availabilityCache;
    }

    @Transactional
    public Rider createRider(CreateRiderRequest request) {
        Rider rider = new Rider(
                request.getFirstName(),
                request.getLastName(),
                request.getPhone(),
                request.getVehicleType(),
                request.getCity(),
                request.getRating(),
                LocalDate.now(),
                request.getCurrentLatitude(),
                request.getCurrentLongitude());
        Rider saved = riderRepository.save(rider);
        availabilityCache.put(saved.getRiderId(), saved.isAvailable());
        return saved;
    }

    @Transactional(readOnly = true)
    public Page<Rider> listRiders(Pageable pageable) {
        return riderRepository.findAll(pageable);
    }

    @Transactional
    public Rider updateAvailability(Long riderId, boolean available) {
        Rider rider = riderRepository.findById(riderId)
                .orElseThrow(() -> new ResourceNotFoundException("Rider not found: " + riderId));
        rider.setAvailable(available);
        Rider saved = riderRepository.save(rider);
        availabilityCache.put(riderId, available); // write-through
        return saved;
    }

    /** Cache-aside read: served entirely from Redis on a hit, Postgres only on a miss. */
    @Transactional(readOnly = true)
    public boolean getAvailability(Long riderId) {
        return availabilityCache.get(riderId).orElseGet(() -> {
            Rider rider = riderRepository.findById(riderId)
                    .orElseThrow(() -> new ResourceNotFoundException("Rider not found: " + riderId));
            availabilityCache.put(riderId, rider.isAvailable());
            return rider.isAvailable();
        });
    }
}
